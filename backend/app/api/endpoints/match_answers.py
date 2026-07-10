from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from openai import APITimeoutError, APIConnectionError, APIStatusError, RateLimitError
import json
import re
import os
import difflib
import asyncio
from datetime import datetime
from typing import AsyncGenerator

from app.api.endpoints.auth import get_current_user
from app.api.endpoints.settings_api import _get_deepseek_model_name
from app.core.user_data import (
    get_user_config_path, get_user_subject,
    get_problems_path, get_answers_path, get_words_path, get_problem_answer_map_path,
)
from app.utils.file_lock import read_json, write_json
from app.utils.ai_client import create_client, DEEPSEEK_BASE_URL

router = APIRouter()


def _safe_extract_json(text: str) -> dict | None:
    """Robust JSON extraction from AI response text with multiple fallback strategies."""
    if not text:
        return None

    cleaned = text.strip()
    # Remove markdown code blocks
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: json5 parse (if available)
    try:
        import json5
        return json5.loads(cleaned)
    except Exception:
        pass

    # Strategy 3: Extract outermost braces
    try:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        pass

    # Strategy 4: Fix common OCR/AI errors
    try:
        fixed = cleaned.replace('：', ':').replace('，', ',').replace('"', '"').replace('"', '"')
        fixed = re.sub(r"(?<!\\)'", '"', fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None


# ========== 本地预对齐辅助函数 ==========

_NUMBER_RE = re.compile(r'(?:^|\n)\s*(\d{1,3})[\.、\)\]］】]\s*')
_PAREN_NUMBER_RE = re.compile(r'(?:^|\n)\s*[（(](\d{1,3})[)）]\s*')
_ANSWER_MARKER_RE = re.compile(r'(?:【答案】|答案\s*[:：]|Key\s*[:：]|Answer\s*[:：])(.*?)(?=\n\s*(?:\d+[\.、\)\]]|【答案】|答案\s*[:：]|Key\s*[:：]|Answer\s*[:：])|$)', re.DOTALL)


def _extract_number_prefix(text: str) -> str | None:
    """从条目开头提取题号，如 '1.' -> '1'，'(1)' -> '1'。"""
    if not text:
        return None
    m = _NUMBER_RE.match(text)
    if m:
        return m.group(1)
    m = _PAREN_NUMBER_RE.match(text)
    if m:
        return m.group(1)
    return None


def _extract_answer_body(text: str) -> str:
    """从答案条目中提取答案主体（【答案】后的内容）。"""
    if not text:
        return text
    m = _ANSWER_MARKER_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _text_similarity(a: str, b: str) -> float:
    """计算两段文本的相似度（0-1）。"""
    if not a or not b:
        return 0.0
    a = re.sub(r'\s+', ' ', a).strip().lower()
    b = re.sub(r'\s+', ' ', b).strip().lower()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _local_align_items(prob_list: list[dict], ans_list: list[dict], similarity_threshold: float = 0.55) -> list[dict]:
    """基于题号和文本相似度做本地预对齐，返回 [{"p_id": ..., "a_id": ...}]。

    策略：
    1. 如果题目和答案都有清晰题号，按题号一一对应；
    2. 否则，对每道题找相似度最高的答案（保守阈值）。
    """
    matches = []
    # 收集题号
    prob_by_num = {}
    ans_by_num = {}
    prob_no_num = []
    ans_no_num = []

    for p in prob_list:
        num = _extract_number_prefix(p.get('content', '')[:200])
        if num:
            prob_by_num.setdefault(num, []).append(p)
        else:
            prob_no_num.append(p)

    for a in ans_list:
        num = _extract_number_prefix(a.get('content', '')[:200])
        if num:
            ans_by_num.setdefault(num, []).append(a)
        else:
            ans_no_num.append(a)

    # 按题号对齐
    for num, ps in prob_by_num.items():
        if num not in ans_by_num:
            continue
        # 一题可能对多答案（保守：只取第一个）
        for p in ps:
            for a in ans_by_num[num]:
                matches.append({"p_id": p["id"], "a_id": a["id"]})

    # 无题号的，按文本相似度对齐
    used_a_ids = {m["a_id"] for m in matches}
    for p in prob_no_num:
        best_a = None
        best_score = 0.0
        p_text = p.get('content', '')[:500]
        for a in ans_no_num + [a for num_ans in ans_by_num.values() for a in num_ans]:
            if a["id"] in used_a_ids:
                continue
            a_text = a.get('content', '')[:500]
            score = _text_similarity(p_text, a_text)
            if score > best_score:
                best_score = score
                best_a = a
        if best_a and best_score >= similarity_threshold:
            matches.append({"p_id": p["id"], "a_id": best_a["id"]})
            used_a_ids.add(best_a["id"])

    return matches


FILENAME_MATCH_PROMPT = """你是试卷文件名匹配助手。将题目文件（学生版）与答案文件（答案版/教师版/答案来源版）配对。
同一份试卷的题目和答案文件名通常相似，只是前缀不同。

重要规则：
- 请返回数据库中的原始完整文件名，不要修改、缩短、合并或省略前缀。
- 题目文件必须来自“题目文件”列表，答案文件必须来自“答案文件”列表。
- 如果同一核心文件名有多个版本（如学生版、教师版），请根据前缀区分：学生版/题目版/空白版/练习版是题目文件，教师版/答案版/答案来源版/解析版/含答案是答案文件。
- 优先匹配核心文件名完全相同或高度相似的一对。

题目文件：
{prob_files}

答案文件：
{ans_files}

输出JSON：{{"m": [{{"p": "题目名", "a": "答案名"}}]}}
字段说明：m=matches匹配列表, p=problem_file题目文件, a=answer_file答案文件
只输出JSON，不要加任何解释。"""

ITEM_MATCH_PROMPT = """你是英语题目答案匹配助手。请将题目与答案按内容对应起来。

题目文件：{prob_file}
答案文件：{ans_file}

题目列表：
{prob_texts}

答案列表：
{ans_texts}

## 匹配规则（按优先级）
1. 先看题号：如果题目和答案条目开头有相同数字题号，优先对应。
2. 再看题干关键词：答案条目中通常包含题目原文或高度相似的句子。
3. 最后看【答案】标记：答案条目中常有“【答案】...”或“答案：...”。

## 输出格式
输出JSON：{{"m": [{{"p": "p1", "a": "a1"}}]}}
字段说明：m=matches匹配列表, p=题目短编号, a=答案短编号
- 只输出能确定对应的条目
- 无法确定的不要输出
- 一题可对应多答案，但不要乱对应

只输出JSON，不要加任何解释。"""


def _today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _get_source_file(item: dict) -> str:
    return item.get("source_file") or item.get("filename") or ""


async def cleanup_matches_after_deletion(username: str, subject: str) -> None:
    """删除题目或答案后，清理 problem_answer_map 中的失效对应关系。

    会同时清理：
    1. 已不存在题目/答案 ID 的 item 级映射
    2. 已不存在题目/答案文件的 file pair 记录
    """
    problems = await read_json(get_problems_path(username, subject)) or []
    answers = await read_json(get_answers_path(username, subject)) or []

    valid_prob_ids = {p["id"] for p in problems if p.get("id")}
    valid_ans_ids = {a["id"] for a in answers if a.get("id")}

    valid_prob_files = {
        _get_source_file(p) for p in problems
        if _get_source_file(p)
    }
    valid_ans_files = {
        _get_source_file(a) for a in answers
        if _get_source_file(a)
    }

    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    p2a = mapping.get("problem_id_to_answer_ids", {})
    a2p = mapping.get("answer_id_to_problem_ids", {})
    matched_files = mapping.get("matched_files", [])

    # 1. 保留两端 ID 都仍然存在的映射
    new_p2a = {}
    for pid, aids in p2a.items():
        if pid not in valid_prob_ids:
            continue
        kept_aids = [aid for aid in aids if aid in valid_ans_ids]
        if kept_aids:
            new_p2a[pid] = kept_aids

    new_a2p = {}
    for aid, pids in a2p.items():
        if aid not in valid_ans_ids:
            continue
        kept_pids = [pid for pid in pids if pid in valid_prob_ids]
        if kept_pids:
            new_a2p[aid] = kept_pids

    # 2. 保留两端文件都仍然存在的 file pair
    new_matched_files = []
    for mf in matched_files:
        ap = mf.get("actual_problem_file") or mf.get("problem_file", "")
        aa = mf.get("actual_answer_file") or mf.get("answer_file", "")
        if ap in valid_prob_files and aa in valid_ans_files:
            new_matched_files.append(mf)

    await write_json(get_problem_answer_map_path(username, subject), {
        "problem_id_to_answer_ids": new_p2a,
        "answer_id_to_problem_ids": new_a2p,
        "matched_files": new_matched_files,
    })


def _fuzzy_find_key(ai_name: str, available_keys: list[str]) -> str | None:
    """模糊查找 AI 返回的文件名在可用键列表中的最佳匹配。"""
    if not ai_name or not available_keys:
        return None

    ai_name = ai_name.strip()
    if not ai_name:
        return None

    # 1. 精确匹配
    if ai_name in available_keys:
        return ai_name

    ai_lower = ai_name.lower().strip()
    ai_root = os.path.splitext(ai_name)[0].lower().strip()
    ai_root_clean = re.sub(r'\s+', ' ', ai_root)

    # 2. 忽略大小写
    for k in available_keys:
        if k.lower().strip() == ai_lower:
            return k

    # 3. 忽略大小写 + 扩展名
    for k in available_keys:
        k_root = os.path.splitext(k)[0].lower().strip()
        k_root_clean = re.sub(r'\s+', ' ', k_root)
        if k_root_clean == ai_root_clean:
            return k

    # 4. 一方包含另一方
    for k in available_keys:
        k_lower = k.lower().strip()
        if ai_lower in k_lower or k_lower in ai_lower:
            return k

    # 5. 去掉扩展名后包含
    for k in available_keys:
        k_root = os.path.splitext(k)[0].lower().strip()
        k_root_clean = re.sub(r'\s+', ' ', k_root)
        if ai_root_clean in k_root_clean or k_root_clean in ai_root_clean:
            return k

    # 6. 相似度匹配（SequenceMatcher），避免单纯包含导致误配
    best_key = None
    best_ratio = 0.0
    for k in available_keys:
        ratio = difflib.SequenceMatcher(None, ai_root_clean, os.path.splitext(k)[0].lower().strip()).ratio()
        if ratio > best_ratio and ratio >= 0.85:
            best_ratio = ratio
            best_key = k
    if best_key:
        return best_key

    # 7. 去掉版本前缀后匹配核心文件名（处理学生版/教师版/答案版等前缀差异）
    VERSION_PREFIXES = [
        r'学生版\s*', r'教师版\s*', r'答案版\s*', r'答案来源版\s*',
        r'解析版\s*', r'详解版\s*', r'讲解版\s*', r'答案\s*', r'题目版\s*',
        r'校本\s*', r'学案\s*', r'练习版\s*', r'空白版\s*', r'含答案\s*',
        r'预习版\s*', r'作业版\s*',
    ]
    def clean_prefixes(name: str) -> str:
        n = name.lower().strip()
        for pat in VERSION_PREFIXES:
            n = re.sub(rf'^\s*{pat}', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\s+', ' ', n)
        n = os.path.splitext(n)[0].strip()
        return n

    ai_core = clean_prefixes(ai_name)
    if ai_core:
        # 7.1 精确核心匹配
        for k in available_keys:
            if clean_prefixes(k) == ai_core:
                return k
        # 7.2 核心相似度匹配（避免前缀相同就误配）
        best_key = None
        best_ratio = 0.0
        for k in available_keys:
            k_core = clean_prefixes(k)
            ratio = difflib.SequenceMatcher(None, ai_core, k_core).ratio()
            if ratio > best_ratio and ratio >= 0.80:
                best_ratio = ratio
                best_key = k
        if best_key:
            return best_key

    return None



def _matched_files_filter(prob_filenames: list[str], ans_filenames: list[str], matched_files: list) -> tuple[list[str], list[str], list[dict]]:
    """过滤已匹配的文件。返回 (剩余题目文件名, 剩余答案文件名, 已匹配列表)。
    
    同时返回更新后的 matched_files：将 AI 返回名映射为实际键名。
    """
    if not matched_files:
        return prob_filenames, ans_filenames, []

    prob_exact = set()
    ans_exact = set()
    updated_mf = []

    for mf in matched_files:
        ap = mf.get("actual_problem_file", mf.get("problem_file", ""))
        aa = mf.get("actual_answer_file", mf.get("answer_file", ""))
        if ap:
            prob_exact.add(ap)
        if aa:
            ans_exact.add(aa)
        updated_mf.append(mf)

    remaining_prob = [f for f in prob_filenames if f not in prob_exact]
    remaining_ans = [f for f in ans_filenames if f not in ans_exact]

    # 对旧格式没有 actual_* 字段的做兼容：用模糊匹配查找
    if not prob_exact and not ans_exact:
        return prob_filenames, ans_filenames, matched_files

    return remaining_prob, remaining_ans, updated_mf


async def _call_deepseek(api_key: str, model_name: str, system: str, prompt: str, timeout: int, max_tokens: int = 8192) -> str:
    client = create_client(api_key, DEEPSEEK_BASE_URL, timeout)
    response = await client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=max_tokens,
        extra_body={"thinking": {"type": "disabled"}},
    )
    text = response.choices[0].message.content or ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    if cleaned.endswith("```"):
        cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


async def _call_deepseek_stream(
    api_key: str, model_name: str, system: str, prompt: str,
    timeout: int, max_tokens: int = 16384,
) -> AsyncGenerator[str, None]:
    """Streaming version of _call_deepseek. Yields each content token as it arrives."""
    client = create_client(api_key, DEEPSEEK_BASE_URL, timeout)
    stream = await client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=max_tokens,
        stream=True,
        extra_body={"thinking": {"type": "disabled"}},
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


async def _match_single_pair(
    q: asyncio.Queue,
    pair_idx: int,
    total_pairs: int,
    pair: dict,
    prob_by_file: dict,
    ans_by_file: dict,
    p2a: dict,
    a2p: dict,
    api_key: str,
    model_name: str,
    timeout: int,
) -> dict:
    """Match a single problem/answer file pair and update mappings.

    Returns {"matched": int, "unmatched_problems": int, "unmatched_answers": int, "confidence": float}.
    """
    ai_prob_file = pair.get("ai_problem_file") or pair.get("actual_problem_file") or pair.get("problem_file", "")
    ai_ans_file = pair.get("ai_answer_file") or pair.get("actual_answer_file") or pair.get("answer_file", "")
    prob_file = pair.get("actual_problem_file") or pair.get("problem_file", "")
    ans_file = pair.get("actual_answer_file") or pair.get("answer_file", "")

    prob_list = prob_by_file.get(prob_file, [])
    ans_list = ans_by_file.get(ans_file, [])
    if not prob_list or not ans_list:
        await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] {ai_prob_file} ←→ {ai_ans_file}（无数据，跳过）"})
        return {"matched": 0, "unmatched_problems": len(prob_list), "unmatched_answers": len(ans_list), "confidence": 0.0}

    await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] 正在匹配：{ai_prob_file} ←→ {ai_ans_file}（{len(prob_list)}题，{len(ans_list)}答）"})

    # ---- 步骤 1：AI 辅助对齐（全部条目，优先使用 AI）----
    # 生成短编号映射，减少 Prompt Tokens
    p_alias_to_id = {f"p{i+1}": p["id"] for i, p in enumerate(prob_list)}
    a_alias_to_id = {f"a{i+1}": a["id"] for i, a in enumerate(ans_list)}
    p_id_to_alias = {p["id"]: alias for alias, p in zip(p_alias_to_id.keys(), prob_list)}
    a_id_to_alias = {a["id"]: alias for alias, a in zip(a_alias_to_id.keys(), ans_list)}

    matched_p_ids = set()
    matched_a_ids = set()
    ai_matches = []

    if prob_list and ans_list:
        prob_texts = "\n".join([f"[{p_id_to_alias[p['id']]}] {p.get('content', '')[:800]}" for p in prob_list])
        ans_texts = "\n".join([f"[{a_id_to_alias[a['id']]}] {a.get('content', '')[:800]}" for a in ans_list])

        try:
            prompt = ITEM_MATCH_PROMPT.format(
                prob_file=ai_prob_file, ans_file=ai_ans_file,
                prob_texts=prob_texts, ans_texts=ans_texts,
            )
            await q.put({"type": "ai_token_reset", "pair_idx": pair_idx})
            collected = []
            stream_gen = _call_deepseek_stream(api_key, model_name, "你是英语题目答案匹配助手，输出JSON。无法匹配的跳过。", prompt, timeout, max_tokens=16384)
            async for token in stream_gen:
                collected.append(token)
                await q.put({"type": "ai_token", "text": token, "pair_idx": pair_idx})
            text = "".join(collected)
            result = _safe_extract_json(text)
            if result is not None:
                for m in result.get("m", []) or result.get("matches", []):
                    p_ref = m.get("p", "") or m.get("p_id", "")
                    a_ref = m.get("a", "") or m.get("a_id", "")
                    # 优先按短编号查找，兼容直接返回 UUID 的情况
                    pid = p_alias_to_id.get(p_ref)
                    if not pid and p_ref in p_id_to_alias:
                        pid = p_ref
                    aid = a_alias_to_id.get(a_ref)
                    if not aid and a_ref in a_id_to_alias:
                        aid = a_ref
                    if pid and aid:
                        ai_matches.append({"p_id": pid, "a_id": aid})
            if ai_matches:
                await q.put({"type": "text", "text": f"    AI 匹配 {len(ai_matches)} 条"})
            await q.put({"type": "ai_token_done", "pair_idx": pair_idx})
        except (asyncio.TimeoutError, TimeoutError):
            await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] AI 匹配超时，将启用本地兜底"})
            await q.put({"type": "ai_token_done", "pair_idx": pair_idx})
        except json.JSONDecodeError:
            await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] AI 返回格式错误，将启用本地兜底"})
            await q.put({"type": "ai_token_done", "pair_idx": pair_idx})
        except Exception as e:
            await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] AI 匹配出错: {str(e)[:80]}，将启用本地兜底"})
            await q.put({"type": "ai_token_done", "pair_idx": pair_idx})

    for m in ai_matches:
        pid = m["p_id"]
        aid = m["a_id"]
        if pid not in p2a: p2a[pid] = []
        if aid not in p2a[pid]: p2a[pid].append(aid)
        if aid not in a2p: a2p[aid] = []
        if pid not in a2p[aid]: a2p[aid].append(pid)
        matched_p_ids.add(pid)
        matched_a_ids.add(aid)

    # ---- 步骤 2：本地兜底（针对 AI 未匹配或 AI 失败的情况）----
    unmatched_prob_list = [p for p in prob_list if p["id"] not in matched_p_ids]
    unmatched_ans_list = [a for a in ans_list if a["id"] not in matched_a_ids]

    local_matches = []
    if unmatched_prob_list and unmatched_ans_list:
        local_matches = _local_align_items(unmatched_prob_list, unmatched_ans_list)
        for m in local_matches:
            pid = m["p_id"]
            aid = m["a_id"]
            if pid not in p2a: p2a[pid] = []
            if aid not in p2a[pid]: p2a[pid].append(aid)
            if aid not in a2p: a2p[aid] = []
            if pid not in a2p[aid]: a2p[aid].append(pid)
            matched_p_ids.add(pid)
            matched_a_ids.add(aid)
        if local_matches:
            await q.put({"type": "text", "text": f"    本地兜底匹配 {len(local_matches)} 条"})

    pair_matched = len(matched_p_ids)
    unmatched_problems = len(prob_list) - len(matched_p_ids)
    unmatched_answers = len(ans_list) - len(matched_a_ids)
    confidence = pair_matched / max(len(prob_list), len(ans_list), 1)

    # 数量/置信度提示
    if len(prob_list) != len(ans_list):
        await q.put({"type": "text", "text": f"    ⚠ 题目数({len(prob_list)})与答案数({len(ans_list)})不一致，请检查"})
    if confidence < 0.5 and pair_matched > 0:
        await q.put({"type": "text", "text": f"    ⚠ 匹配率较低（{int(confidence * 100)}%），建议人工核对"})

    if pair_matched == 0:
        await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] 未找到匹配"})
    else:
        await q.put({"type": "text", "text": f"  [{pair_idx+1}/{total_pairs}] 完成，匹配 {pair_matched} 条（未匹配题 {unmatched_problems}，未匹配答 {unmatched_answers}）"})

    return {"matched": pair_matched, "unmatched_problems": unmatched_problems, "unmatched_answers": unmatched_answers, "confidence": confidence}


@router.post("/run")
async def match_answers(
    data: dict,
    username: str = Depends(get_current_user),
):
    mode = data.get("mode", "all")
    source_files = data.get("source_files", [])

    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()

        async def worker():
            try:
                config = await read_json(get_user_config_path(username)) or {}
                api_key = config.get("deepseek_api_key", "")
                if not api_key:
                    await q.put({"type": "error", "text": "DeepSeek API Key 未配置"})
                    return
                model_choice = config.get("deepseek_model", "flash")
                model_name = _get_deepseek_model_name(model_choice)
                timeout = max(int(config.get("deepseek_timeout", 60) or 60), 180)

                subject = await get_user_subject(username)
                problems = await read_json(get_problems_path(username, subject)) or []
                answers = await read_json(get_answers_path(username, subject)) or []
                existing_map = await read_json(get_problem_answer_map_path(username, subject)) or {}
                p2a = existing_map.get("problem_id_to_answer_ids", {})
                a2p = existing_map.get("answer_id_to_problem_ids", {})
                matched_files = existing_map.get("matched_files", [])

                if mode == "today":
                    today = _today_prefix()
                    problems = [p for p in problems if p.get("created_at", "").startswith(today)]
                    answers = [a for a in answers if a.get("created_at", "").startswith(today)]

                if source_files:
                    problems = [p for p in problems if _get_source_file(p) in source_files]
                    answers = [a for a in answers if _get_source_file(a) in source_files]

                if not problems:
                    await q.put({"type": "error", "text": "没有题目数据，请先上传题目类型的文档"})
                    return
                if not answers:
                    await q.put({"type": "error", "text": "没有答案数据，请先上传答案类型的文档"})
                    return

                prob_by_file = {}
                for p in problems:
                    sf = _get_source_file(p)
                    if not sf:
                        sf = f"__unnamed_prob_{p.get('id', '')}"
                    if sf not in prob_by_file:
                        prob_by_file[sf] = []
                    prob_by_file[sf].append(p)

                ans_by_file = {}
                for a in answers:
                    sf = _get_source_file(a)
                    if not sf:
                        sf = f"__unnamed_ans_{a.get('id', '')}"
                    if sf not in ans_by_file:
                        ans_by_file[sf] = []
                    ans_by_file[sf].append(a)

                prob_filenames = sorted(prob_by_file.keys())
                ans_filenames = sorted(ans_by_file.keys())

                await q.put({"type": "text", "text": f"准备匹配：{len(problems)} 道题目（来自 {len(prob_filenames)} 个文件），{len(answers)} 条答案（来自 {len(ans_filenames)} 个文件）"})

                # 已匹配过的文件在后续匹配中跳过（除非 force=true）
                force = data.get("force", False)
                if not force:
                    prob_filenames, ans_filenames, matched_files = _matched_files_filter(
                        prob_filenames, ans_filenames, matched_files
                    )

                if not prob_filenames:
                    await q.put({"type": "text", "text": "所有题目文件已匹配完成，无需再次匹配"})
                    # 尝试内容匹配：如果还有未匹配的题目，可能是跨文件匹配
                    prob_remaining = [f for f in prob_by_file.keys() if f not in {mf.get("actual_problem_file", mf.get("problem_file", "")) for mf in matched_files}]
                    ans_remaining = [f for f in ans_by_file.keys() if f not in {mf.get("actual_answer_file", mf.get("answer_file", "")) for mf in matched_files}]
                    if prob_remaining or ans_remaining:
                        await q.put({"type": "text", "text": f"仍有 {len(prob_remaining)} 个题目文件和 {len(ans_remaining)} 个答案文件未匹配，尝试跨文件内容匹配..."})
                        # 将剩余的所有题目和答案合入
                        prob_filenames = prob_remaining
                        ans_filenames = ans_remaining
                    else:
                        await q.put({"type": "result", "matched": 0, "file_pairs": 0})
                        return

                if not ans_filenames:
                    await q.put({"type": "text", "text": "所有答案文件已匹配完成，无需再次匹配"})
                    ans_remaining = [f for f in ans_by_file.keys() if f not in {mf.get("actual_answer_file", mf.get("answer_file", "")) for mf in matched_files}]
                    prob_remaining = [f for f in prob_by_file.keys() if f not in {mf.get("actual_problem_file", mf.get("problem_file", "")) for mf in matched_files}]
                    if ans_remaining or prob_remaining:
                        await q.put({"type": "text", "text": f"仍有 {len(prob_remaining)} 个题目文件和 {len(ans_remaining)} 个答案文件未匹配，尝试跨文件内容匹配..."})
                        prob_filenames = prob_remaining
                        ans_filenames = ans_remaining
                    else:
                        await q.put({"type": "result", "matched": 0, "file_pairs": 0})
                        return

                # ---- 第一阶段：文件名级匹配 ----
                await q.put({"type": "text", "text": "第一阶段：AI正在匹配文件名..."})
                try:
                    prompt = FILENAME_MATCH_PROMPT.format(
                        prob_files="\n".join(prob_filenames),
                        ans_files="\n".join(ans_filenames),
                    )
                    text = await asyncio.wait_for(
                        _call_deepseek(api_key, model_name, "你是试卷文件名匹配助手，输出JSON。", prompt, timeout),
                        timeout=max(timeout, 60),
                    )
                    result = _safe_extract_json(text)
                    if result is None:
                        raise json.JSONDecodeError("无法解析文件名匹配结果", text, 0)
                    file_matches = result.get("m", []) or result.get("matches", [])
                except asyncio.TimeoutError:
                    await q.put({"type": "error", "text": "AI文件名匹配超时，请增大DeepSeek超时设置后重试"})
                    return
                except Exception as e:
                    await q.put({"type": "error", "text": f"AI文件名匹配失败: {str(e)[:100]}"})
                    return

                await q.put({"type": "text", "text": f"文件名匹配完成，找到 {len(file_matches)} 对文件："})
                for fm in file_matches:
                    pf = fm.get("p", "") or fm.get("problem_file", "")
                    af = fm.get("a", "") or fm.get("answer_file", "")
                    if pf and af:
                        await q.put({"type": "text", "text": f"  {pf} ←→ {af}"})

                if not file_matches:
                    await q.put({"type": "error", "text": "AI未能匹配任何文件对，请检查题目和答案的文件名是否对应"})
                    return

                # ---- 第二阶段：将 AI 返回的文件名模糊匹配到实际键名 ----
                resolved_pairs = []
                for fm in file_matches:
                    pf = fm.get("p", "") or fm.get("problem_file", "")
                    af = fm.get("a", "") or fm.get("answer_file", "")
                    if not pf or not af:
                        continue
                    actual_pf = _fuzzy_find_key(pf, prob_filenames)
                    actual_af = _fuzzy_find_key(af, ans_filenames)
                    if actual_pf and actual_af:
                        resolved_pairs.append({
                            "ai_problem_file": pf,
                            "ai_answer_file": af,
                            "actual_problem_file": actual_pf,
                            "actual_answer_file": actual_af,
                        })
                    else:
                        reason = []
                        if not actual_pf:
                            reason.append(f"题目文件「{pf}」未在数据库中找到")
                        if not actual_af:
                            reason.append(f"答案文件「{af}」未在数据库中找到")
                        await q.put({"type": "text", "text": f"  ⚠ 跳过 {'；'.join(reason)}。AI返回的文件名：题「{pf}」答「{af}」。当前可用题目文件（前10个）：{prob_filenames[:10]}；当前可用答案文件（前10个）：{ans_filenames[:10]}"})

                if not resolved_pairs:
                    await q.put({"type": "error", "text": "AI匹配的文件名在数据库中找不到对应记录，匹配终止"})
                    return

                # ---- 第三阶段：逐对匹配（最多3并发） ----
                total_matched = 0
                new_file_pairs = []
                total_pairs = len(resolved_pairs)
                match_sem = asyncio.Semaphore(5)

                async def _match_one_wrapped(i, pair):
                    nonlocal total_matched
                    async with match_sem:
                        pair_result = await _match_single_pair(
                            q, i, total_pairs, pair, prob_by_file, ans_by_file, p2a, a2p, api_key, model_name, timeout
                        )
                        pair_matched = pair_result.get("matched", 0)
                        if pair_matched > 0:
                            new_file_pairs.append({
                                "problem_file": pair.get("ai_problem_file") or pair.get("problem_file", ""),
                                "answer_file": pair.get("ai_answer_file") or pair.get("answer_file", ""),
                                "actual_problem_file": pair.get("actual_problem_file") or pair.get("problem_file", ""),
                                "actual_answer_file": pair.get("actual_answer_file") or pair.get("answer_file", ""),
                            })
                        total_matched += pair_matched

                await asyncio.gather(*[_match_one_wrapped(i, pair) for i, pair in enumerate(resolved_pairs)])

                if new_file_pairs:
                    matched_files.extend(new_file_pairs)
                    await write_json(get_problem_answer_map_path(username, subject), {
                        "problem_id_to_answer_ids": p2a,
                        "answer_id_to_problem_ids": a2p,
                        "matched_files": matched_files,
                    })
                    await q.put({"type": "result", "matched": total_matched, "file_pairs": len(new_file_pairs)})
                else:
                    await q.put({"type": "error", "text": "未产生任何匹配结果"})
            except Exception as e:
                await q.put({"type": "error", "text": f"匹配过程异常: {str(e)[:200]}"})
            finally:
                await q.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                if item.get("type") in ("result", "error"):
                    yield "data: [DONE]\n\n"
                    break
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/for-problem/{problem_id}")
async def get_matched_answer(
    problem_id: str,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    p2a = mapping.get("problem_id_to_answer_ids", {})
    answer_ids = p2a.get(problem_id, [])
    if not answer_ids:
        return {"answers": []}
    answers = await read_json(get_answers_path(username, subject)) or []
    ans_map = {a["id"]: a for a in answers}
    result = []
    for aid in answer_ids:
        if aid in ans_map:
            result.append(ans_map[aid])
    return {"answers": result}


@router.get("/for-answer/{answer_id}")
async def get_matched_problem(
    answer_id: str,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    a2p = mapping.get("answer_id_to_problem_ids", {})
    problem_ids = a2p.get(answer_id, [])
    if not problem_ids:
        return {"problems": []}
    problems = await read_json(get_problems_path(username, subject)) or []
    prob_map = {p["id"]: p for p in problems}
    result = []
    for pid in problem_ids:
        if pid in prob_map:
            result.append(prob_map[pid])
    return {"problems": result}


@router.post("/run-word-match")
async def match_word_lists(
    data: dict,
    username: str = Depends(get_current_user),
):
    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()
        async def worker():
            try:
                subject = await get_user_subject(username)
                word_lists = await read_json(get_words_path(username, subject)) or []
                student_words = [w for w in word_lists if w.get("is_student") and not w.get("matched_teacher_id")]
                teacher_words = [w for w in word_lists if not w.get("is_student") and w.get("words")]
                if not student_words:
                    await q.put({"type": "text", "text": "没有待匹配的学生版词单"})
                    await q.put({"type": "result", "matched": 0, "file_pairs": 0})
                    return
                if not teacher_words:
                    await q.put({"type": "text", "text": "没有教师版/答案版词单可用于匹配"})
                    await q.put({"type": "result", "matched": 0, "file_pairs": 0})
                    return
                await q.put({"type": "text", "text": f"匹配词单：{len(student_words)} 个学生版 → {len(teacher_words)} 个教师版"})
                word_matches = 0
                for sw in student_words:
                    sname = sw.get("filename", "")
                    base = re.sub(r'学生版\s*', '', sname, flags=re.IGNORECASE)
                    base = os.path.splitext(base)[0].strip().lower()
                    base = re.sub(r'\s+', ' ', base)

                    # 1. 按文件名找候选
                    candidates = []
                    for tw in teacher_words:
                        tname = tw.get("filename", "")
                        tbase = os.path.splitext(tname)[0].strip().lower()
                        tbase = re.sub(r'^答案版\s*|^答案来源版\s*|^教师版\s*|^答案\s*', '', tbase, flags=re.IGNORECASE)
                        tbase = re.sub(r'\s+', ' ', tbase)
                        if tbase == base or base in tbase or tbase in base:
                            candidates.append(tw)

                    # 2. 如果有多个候选，按中文释义重叠度挑选
                    best_match = None
                    if candidates:
                        if len(candidates) == 1:
                            best_match = candidates[0]
                        else:
                            sw_words = sw.get("words", [])
                            sw_chinese = {w.get("chinese", "").strip() for w in sw_words if w.get("chinese", "").strip()}
                            best_overlap = 0
                            for tw in candidates:
                                tw_words = tw.get("words", [])
                                tw_chinese = {w.get("chinese", "").strip() for w in tw_words if w.get("chinese", "").strip()}
                                overlap = len(sw_chinese & tw_chinese) if sw_chinese else 0
                                if overlap > best_overlap:
                                    best_overlap = overlap
                                    best_match = tw
                            if not best_match:
                                best_match = candidates[0]

                    if best_match:
                        sw["matched_teacher_id"] = best_match["id"]
                        word_matches += 1
                        await q.put({"type": "text", "text": f"  ✅ {sw.get('filename','')} ←→ {best_match.get('filename','')}"})
                if word_matches:
                    await write_json(get_words_path(username, subject), word_lists)
                    await q.put({"type": "result", "matched": word_matches, "file_pairs": word_matches})
                else:
                    await q.put({"type": "result", "matched": 0, "file_pairs": 0})
            except Exception as e:
                await q.put({"type": "error", "text": f"词单匹配异常: {str(e)[:200]}"})
            finally:
                await q.put(None)
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                if item.get("type") in ("result", "error"):
                    yield "data: [DONE]\n\n"
                    break
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/word-match/{word_id}")
async def get_word_match(
    word_id: str,
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    student = None
    for w in word_lists:
        if w.get("id") == word_id:
            student = w
            break
    if not student:
        return {"teacher": None}
    teacher_id = student.get("matched_teacher_id")
    if not teacher_id:
        return {"teacher": None}
    for w in word_lists:
        if w.get("id") == teacher_id:
            return {"teacher": w}
    return {"teacher": None}


@router.post("/word-match-manual")
async def set_word_match_manual(
    data: dict,
    username: str = Depends(get_current_user),
):
    """手动设置学生版词单对应的教师版词单。"""
    student_id = data.get("student_word_id")
    teacher_id = data.get("teacher_word_id")
    if not student_id or not teacher_id:
        raise HTTPException(status_code=400, detail="需要提供 student_word_id 和 teacher_word_id")
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    student = next((w for w in word_lists if w.get("id") == student_id), None)
    teacher = next((w for w in word_lists if w.get("id") == teacher_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="学生版词单不存在")
    if not teacher:
        raise HTTPException(status_code=404, detail="教师版词单不存在")
    if not student.get("is_student"):
        raise HTTPException(status_code=400, detail="只能选择学生版词单作为目标")
    if teacher.get("is_student"):
        raise HTTPException(status_code=400, detail="不能选择学生版词单作为对应源")
    student["matched_teacher_id"] = teacher_id
    await write_json(get_words_path(username, subject), word_lists)
    return {"message": "词单对应已保存"}


@router.delete("/word-match-manual")
async def delete_word_match_manual(
    data: dict,
    username: str = Depends(get_current_user),
):
    """取消学生版词单的教师版对应。"""
    student_id = data.get("student_word_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="需要提供 student_word_id")
    subject = await get_user_subject(username)
    word_lists = await read_json(get_words_path(username, subject)) or []
    student = next((w for w in word_lists if w.get("id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="学生版词单不存在")
    if "matched_teacher_id" in student:
        del student["matched_teacher_id"]
    await write_json(get_words_path(username, subject), word_lists)
    return {"message": "词单对应已取消"}


@router.get("/status")
async def get_match_status(
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    p2a = mapping.get("problem_id_to_answer_ids", {})
    matched_files = mapping.get("matched_files", [])
    problems = await read_json(get_problems_path(username, subject)) or []
    answers = await read_json(get_answers_path(username, subject)) or []
    prob_matched = sum(1 for p in problems if p.get("id") in p2a)
    ans_matched = sum(1 for a in answers if a.get("id") in mapping.get("answer_id_to_problem_ids", {}))
    today = _today_prefix()
    today_problems = [p for p in problems if p.get("created_at", "").startswith(today)]
    today_answers = [a for a in answers if a.get("created_at", "").startswith(today)]
    return {
        "total_problems": len(problems),
        "matched_problems": prob_matched,
        "total_answers": len(answers),
        "matched_answers": ans_matched,
        "matched_files": len(matched_files),
        "today_problems": len(today_problems),
        "today_answers": len(today_answers),
    }


@router.post("/reset")
async def reset_matches(
    username: str = Depends(get_current_user),
):
    subject = await get_user_subject(username)
    await write_json(get_problem_answer_map_path(username, subject), {
        "problem_id_to_answer_ids": {},
        "answer_id_to_problem_ids": {},
        "matched_files": [],
    })
    return {"message": "对应关系已清空"}


@router.post("/manual-match")
async def manual_create_match(
    data: dict,
    username: str = Depends(get_current_user),
):
    """Manually create a match between a problem and an answer."""
    problem_id = data.get("problem_id", "")
    answer_id = data.get("answer_id", "")
    if not problem_id or not answer_id:
        raise HTTPException(status_code=400, detail="需要提供 problem_id 和 answer_id")

    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    p2a = mapping.get("problem_id_to_answer_ids", {})
    a2p = mapping.get("answer_id_to_problem_ids", {})

    if problem_id not in p2a:
        p2a[problem_id] = []
    if answer_id not in p2a[problem_id]:
        p2a[problem_id].append(answer_id)
    if answer_id not in a2p:
        a2p[answer_id] = []
    if problem_id not in a2p[answer_id]:
        a2p[answer_id].append(problem_id)

    await write_json(get_problem_answer_map_path(username, subject), {
        "problem_id_to_answer_ids": p2a,
        "answer_id_to_problem_ids": a2p,
        "matched_files": mapping.get("matched_files", []),
    })
    return {"message": "对应成功", "problem_id": problem_id, "answer_id": answer_id}


@router.delete("/manual-match")
async def manual_delete_match(
    data: dict,
    username: str = Depends(get_current_user),
):
    """Delete a manual match between a problem and an answer."""
    problem_id = data.get("problem_id", "")
    answer_id = data.get("answer_id", "")
    if not problem_id or not answer_id:
        raise HTTPException(status_code=400, detail="需要提供 problem_id 和 answer_id")

    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    p2a = mapping.get("problem_id_to_answer_ids", {})
    a2p = mapping.get("answer_id_to_problem_ids", {})

    if problem_id in p2a and answer_id in p2a[problem_id]:
        p2a[problem_id].remove(answer_id)
        if not p2a[problem_id]:
            del p2a[problem_id]
    if answer_id in a2p and problem_id in a2p[answer_id]:
        a2p[answer_id].remove(problem_id)
        if not a2p[answer_id]:
            del a2p[answer_id]

    await write_json(get_problem_answer_map_path(username, subject), {
        "problem_id_to_answer_ids": p2a,
        "answer_id_to_problem_ids": a2p,
        "matched_files": mapping.get("matched_files", []),
    })
    return {"message": "已取消对应", "problem_id": problem_id, "answer_id": answer_id}


@router.get("/unmatched")
async def get_unmatched_items(
    username: str = Depends(get_current_user),
):
    """Get unmatched problems and answers, grouped by source file."""
    subject = await get_user_subject(username)
    problems = await read_json(get_problems_path(username, subject)) or []
    answers = await read_json(get_answers_path(username, subject)) or []
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    p2a = mapping.get("problem_id_to_answer_ids", {})

    unmatched_problems = [p for p in problems if p.get("id") not in p2a]
    all_matched_answer_ids = set()
    for aids in p2a.values():
        all_matched_answer_ids.update(aids)
    unmatched_answers = [a for a in answers if a.get("id") not in all_matched_answer_ids]

    return {
        "problems": unmatched_problems,
        "answers": unmatched_answers,
    }


@router.post("/run-for-pair")
async def match_for_file_pair(
    data: dict,
    username: str = Depends(get_current_user),
):
    """Given a problem filename and an answer filename, run item-level AI matching directly."""
    prob_filename = data.get("problem_filename", "")
    ans_filename = data.get("answer_filename", "")
    if not prob_filename or not ans_filename:
        raise HTTPException(status_code=400, detail="需要提供 problem_filename 和 answer_filename")

    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()

        async def worker():
            try:
                config = await read_json(get_user_config_path(username)) or {}
                api_key = config.get("deepseek_api_key", "")
                if not api_key:
                    await q.put({"type": "error", "text": "DeepSeek API Key 未配置"})
                    return
                model_choice = config.get("deepseek_model", "flash")
                model_name = _get_deepseek_model_name(model_choice)
                timeout = max(int(config.get("deepseek_timeout", 60) or 60), 180)

                subject = await get_user_subject(username)
                problems = await read_json(get_problems_path(username, subject)) or []
                answers = await read_json(get_answers_path(username, subject)) or []
                existing_map = await read_json(get_problem_answer_map_path(username, subject)) or {}
                p2a = existing_map.get("problem_id_to_answer_ids", {})
                a2p = existing_map.get("answer_id_to_problem_ids", {})
                matched_files = existing_map.get("matched_files", [])

                prob_by_file = {}
                for p in problems:
                    sf = _get_source_file(p)
                    if not sf:
                        sf = f"__unnamed_prob_{p.get('id', '')}"
                    prob_by_file.setdefault(sf, []).append(p)

                ans_by_file = {}
                for a in answers:
                    sf = _get_source_file(a)
                    if not sf:
                        sf = f"__unnamed_ans_{a.get('id', '')}"
                    ans_by_file.setdefault(sf, []).append(a)

                pair = {
                    "problem_file": prob_filename,
                    "answer_file": ans_filename,
                    "actual_problem_file": prob_filename,
                    "actual_answer_file": ans_filename,
                }

                await q.put({"type": "text", "text": f"开始匹配：{prob_filename} ←→ {ans_filename}"})
                pair_result = await _match_single_pair(
                    q, 0, 1, pair, prob_by_file, ans_by_file, p2a, a2p, api_key, model_name, timeout
                )
                pair_matched = pair_result.get("matched", 0)

                if pair_matched > 0:
                    # 去重添加 file pair
                    found = False
                    for mf in matched_files:
                        if (mf.get("actual_problem_file", mf.get("problem_file", "")) == prob_filename and
                            mf.get("actual_answer_file", mf.get("answer_file", "")) == ans_filename):
                            found = True
                            break
                    if not found:
                        matched_files.append({
                            "problem_file": prob_filename,
                            "answer_file": ans_filename,
                            "actual_problem_file": prob_filename,
                            "actual_answer_file": ans_filename,
                        })
                    await write_json(get_problem_answer_map_path(username, subject), {
                        "problem_id_to_answer_ids": p2a,
                        "answer_id_to_problem_ids": a2p,
                        "matched_files": matched_files,
                    })
                    await q.put({"type": "result", "matched": pair_matched, "file_pairs": 1, "problem_file": prob_filename, "answer_file": ans_filename})
                else:
                    await q.put({"type": "error", "text": "未产生任何匹配结果"})
            except Exception as e:
                await q.put({"type": "error", "text": f"匹配过程异常: {str(e)[:200]}"})
            finally:
                await q.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                if item.get("type") in ("result", "error"):
                    yield "data: [DONE]\n\n"
                    break
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/file-pairs")
async def list_manual_file_pairs(
    username: str = Depends(get_current_user),
):
    """List all matched file pairs."""
    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    return {"pairs": mapping.get("matched_files", [])}


@router.post("/file-pairs")
async def create_manual_file_pair(
    data: dict,
    username: str = Depends(get_current_user),
):
    """Manually pair a problem file with an answer file, optionally run AI matching."""
    prob_filename = data.get("problem_filename", "")
    ans_filename = data.get("answer_filename", "")
    run_match = data.get("run_match", False)
    if not prob_filename or not ans_filename:
        raise HTTPException(status_code=400, detail="需要提供 problem_filename 和 answer_filename")

    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    matched_files = mapping.get("matched_files", [])

    existing = None
    for mf in matched_files:
        actual_p = mf.get("actual_problem_file", mf.get("problem_file", ""))
        actual_a = mf.get("actual_answer_file", mf.get("answer_file", ""))
        if actual_p == prob_filename and actual_a == ans_filename:
            existing = mf
            break

    new_pair = existing or {
        "problem_file": prob_filename,
        "answer_file": ans_filename,
        "actual_problem_file": prob_filename,
        "actual_answer_file": ans_filename,
    }
    if not existing:
        matched_files.append(new_pair)
        await write_json(get_problem_answer_map_path(username, subject), {
            "problem_id_to_answer_ids": mapping.get("problem_id_to_answer_ids", {}),
            "answer_id_to_problem_ids": mapping.get("answer_id_to_problem_ids", {}),
            "matched_files": matched_files,
        })

    if not run_match:
        return {"message": "文件对应已保存", "pair": new_pair}

    # ---- run AI matching via SSE ----
    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()

        async def worker():
            try:
                yield "data: " + json.dumps({"type": "text", "text": f"文件对应已保存，开始 AI 匹配..."}, ensure_ascii=False) + "\n\n"

                config = await read_json(get_user_config_path(username)) or {}
                api_key = config.get("deepseek_api_key", "")
                if not api_key:
                    await q.put({"type": "error", "text": "DeepSeek API Key 未配置"})
                    return
                model_choice = config.get("deepseek_model", "flash")
                model_name = _get_deepseek_model_name(model_choice)
                timeout = max(int(config.get("deepseek_timeout", 60) or 60), 180)

                problems = await read_json(get_problems_path(username, subject)) or []
                answers = await read_json(get_answers_path(username, subject)) or []
                existing_map = await read_json(get_problem_answer_map_path(username, subject)) or {}
                p2a = existing_map.get("problem_id_to_answer_ids", {})
                a2p = existing_map.get("answer_id_to_problem_ids", {})
                matched_files = existing_map.get("matched_files", [])

                prob_by_file = {}
                for p in problems:
                    sf = _get_source_file(p)
                    if not sf:
                        sf = f"__unnamed_prob_{p.get('id', '')}"
                    prob_by_file.setdefault(sf, []).append(p)

                ans_by_file = {}
                for a in answers:
                    sf = _get_source_file(a)
                    if not sf:
                        sf = f"__unnamed_ans_{a.get('id', '')}"
                    ans_by_file.setdefault(sf, []).append(a)

                pair = {
                    "problem_file": prob_filename,
                    "answer_file": ans_filename,
                    "actual_problem_file": prob_filename,
                    "actual_answer_file": ans_filename,
                }

                await q.put({"type": "text", "text": f"开始匹配：{prob_filename} ←→ {ans_filename}"})
                pair_result = await _match_single_pair(
                    q, 0, 1, pair, prob_by_file, ans_by_file, p2a, a2p, api_key, model_name, timeout
                )
                pair_matched = pair_result.get("matched", 0)

                if pair_matched > 0:
                    found = False
                    for mf in matched_files:
                        if (mf.get("actual_problem_file", mf.get("problem_file", "")) == prob_filename and
                            mf.get("actual_answer_file", mf.get("answer_file", "")) == ans_filename):
                            found = True
                            break
                    if not found:
                        matched_files.append({
                            "problem_file": prob_filename,
                            "answer_file": ans_filename,
                            "actual_problem_file": prob_filename,
                            "actual_answer_file": ans_filename,
                        })
                    await write_json(get_problem_answer_map_path(username, subject), {
                        "problem_id_to_answer_ids": p2a,
                        "answer_id_to_problem_ids": a2p,
                        "matched_files": matched_files,
                    })
                    await q.put({"type": "result", "matched": pair_matched, "file_pairs": 1, "problem_file": prob_filename, "answer_file": ans_filename})
                else:
                    await q.put({"type": "error", "text": "未产生任何匹配结果"})
            except Exception as e:
                await q.put({"type": "error", "text": f"匹配过程异常: {str(e)[:200]}"})
            finally:
                await q.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                if item.get("type") in ("result", "error"):
                    yield "data: [DONE]\n\n"
                    break
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.delete("/file-pairs")
async def delete_manual_file_pair(
    data: dict,
    username: str = Depends(get_current_user),
):
    """Delete a manual file pair."""
    prob_filename = data.get("problem_filename", "")
    ans_filename = data.get("answer_filename", "")
    if not prob_filename or not ans_filename:
        raise HTTPException(status_code=400, detail="需要提供 problem_filename 和 answer_filename")

    subject = await get_user_subject(username)
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    matched_files = mapping.get("matched_files", [])

    matched_files = [
        mf for mf in matched_files
        if not (
            (mf.get("actual_problem_file", mf.get("problem_file", "")) == prob_filename)
            and (mf.get("actual_answer_file", mf.get("answer_file", "")) == ans_filename)
        )
    ]
    await write_json(get_problem_answer_map_path(username, subject), {
        "problem_id_to_answer_ids": mapping.get("problem_id_to_answer_ids", {}),
        "answer_id_to_problem_ids": mapping.get("answer_id_to_problem_ids", {}),
        "matched_files": matched_files,
    })
    return {"message": "已取消文件对应"}


@router.get("/unmatched-files")
async def get_unmatched_files(
    username: str = Depends(get_current_user),
):
    """List problem files and answer files that are not yet matched, plus word list pairing info."""
    subject = await get_user_subject(username)
    problems = await read_json(get_problems_path(username, subject)) or []
    answers = await read_json(get_answers_path(username, subject)) or []
    mapping = await read_json(get_problem_answer_map_path(username, subject)) or {}
    matched_files = mapping.get("matched_files", [])
    word_lists = await read_json(get_words_path(username, subject)) or []

    matched_prob_files = set()
    matched_ans_files = set()
    for mf in matched_files:
        matched_prob_files.add(mf.get("actual_problem_file", mf.get("problem_file", "")))
        matched_ans_files.add(mf.get("actual_answer_file", mf.get("answer_file", "")))

    prob_files = sorted(set(
        p.get("source_file") or p.get("filename", "") for p in problems
        if p.get("source_file") or p.get("filename")
    ))
    ans_files = sorted(set(
        a.get("source_file") or a.get("filename", "") for a in answers
        if a.get("source_file") or a.get("filename")
    ))

    student_words = [w for w in word_lists if w.get("is_student")]
    teacher_words = [w for w in word_lists if not w.get("is_student")]
    word_pairs = []
    for sw in student_words:
        tid = sw.get("matched_teacher_id")
        if tid:
            tw = next((w for w in teacher_words if w.get("id") == tid), None)
            if tw:
                word_pairs.append({
                    "student_word_id": sw["id"],
                    "student_filename": sw.get("filename", ""),
                    "teacher_word_id": tw["id"],
                    "teacher_filename": tw.get("filename", ""),
                })

    return {
        "problem_files": [f for f in prob_files if f not in matched_prob_files],
        "answer_files": [f for f in ans_files if f not in matched_ans_files],
        "all_problem_files": prob_files,
        "all_answer_files": ans_files,
        "pairs": matched_files,
        "word_student_files": [{"id": w["id"], "filename": w.get("filename", "")} for w in student_words if not w.get("matched_teacher_id")],
        "word_teacher_files": [{"id": w["id"], "filename": w.get("filename", "")} for w in teacher_words],
        "word_pairs": word_pairs,
    }
