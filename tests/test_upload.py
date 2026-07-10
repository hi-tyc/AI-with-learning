import httpx
import json
import asyncio
import os

files_path = r'C:\Users\朵朵\Desktop\英语复习资料'

test_files = [
    '现在完成时 知识梳理.docx',
    '学生版 南外初一下 期末 单选基础练习.docx',
    '答案来源版 南外初一下 期末 单句首字母填空 E1 U12-U13.docx',
]

async def upload_file(client, fname, tag, semester):
    fpath = os.path.join(files_path, fname)
    if not os.path.exists(fpath):
        print(f'  [SKIP] File not found: {fpath}')
        return

    with open(fpath, 'rb') as f:
        file_data = f.read()
    print(f'  File size: {len(file_data)} bytes')

    boundary = '----TestBoundary789'
    body_parts = []
    body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\nContent-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n'.encode())
    body_parts.append(file_data)
    body_parts.append(f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="tag"\r\n\r\n{tag}\r\n'.encode())
    body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="semester"\r\n\r\n{semester}\r\n'.encode())
    body_parts.append(f'\r\n--{boundary}--\r\n'.encode())
    body = b''.join(body_parts)

    resp = await client.post(
        'http://localhost:6003/api/english-upload/classify',
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        content=body,
        timeout=180
    )

    print(f'  Response status: {resp.status_code}')
    if resp.status_code == 200:
        text = resp.text
        for line in text.split('\n\n'):
            line = line.strip()
            if line.startswith('data: '):
                payload = line[6:]
                if payload == '[DONE]':
                    break
                try:
                    msg = json.loads(payload)
                    t = msg.get('type')
                    if t == 'result':
                        print(f'  >>> RESULT:')
                        print(f'      doc_type:   {msg.get("doc_type")}')
                        print(f'      confidence: {msg.get("confidence")}')
                        print(f'      summary:    {msg.get("summary","")}')
                        print(f'      reason:     {msg.get("reason")}')
                        print(f'      tag:        {msg.get("tag")}')
                        print(f'      count:      {msg.get("count")}')
                    elif t == 'text':
                        txt = msg.get('text', '').strip()
                        if txt:
                            print(f'  > {txt[:120]}')
                    elif t == 'error':
                        print(f'  >>> ERROR: {msg.get("text","")}')
                except json.JSONDecodeError:
                    pass
    else:
        print(f'  Error: {resp.text[:300]}')


async def main():
    async with httpx.AsyncClient() as client:
        # Login
        print('=== Logging in... ===')
        resp = await client.post('http://localhost:6003/api/auth/login',
            json={'username': 'test_english', 'password': 'dummy', 'subject': '英语'})
        print(f'Login: {resp.status_code} {resp.json()}')

        # File 1: Knowledge review -> should be 资料
        print('\n=== Test 1: 现在完成时 知识梳理 ===')
        print('  Expect: 资料 (review material)')
        await upload_file(client, '现在完成时 知识梳理.docx', '期末', '25-26 第一学期')

        # File 2: Student practice -> could be 题目
        print('\n=== Test 2: 学生版 单选基础练习 ===')
        print('  Expect: 题目 (problems/exercises)')
        await upload_file(client, '学生版 南外初一下 期末 单选基础练习.docx', '期末', '25-26 第一学期')

        # File 3: Answer key -> should be 答案
        print('\n=== Test 3: 答案来源版 首字母填空 ===')
        print('  Expect: 答案 (answer key)')
        await upload_file(client, '答案来源版 南外初一下 期末 单句首字母填空 E1 U12-U13.docx', '期末', '25-26 第一学期')

    print('\n=== Done ===')

asyncio.run(main())
