import MarkdownIt from 'markdown-it'
import katex from 'katex'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

function renderKatex(expr, displayMode) {
  try {
    return katex.renderToString(expr, { displayMode, throwOnError: false, errorColor: '#cc0000' })
  } catch (e) {
    const safe = String(expr).replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return displayMode ? `<div class="katex-error">${safe}</div>` : `<span class="katex-error">${safe}</span>`
  }
}

// Render markdown + LaTeX math to HTML (for v-html).
export function renderMath(text) {
  if (text == null) return ''
  let src = String(text)
  const stash = []
  const put = (html) => { stash.push(html); return `zZkatexZz${stash.length - 1}zZendZz` }
  // Order matters: block first, then inline.
  src = src.replace(/\$\$([\s\S]+?)\$\$/g, (_, e) => put(renderKatex(e.trim(), true)))
  src = src.replace(/\\\[([\s\S]+?)\\\]/g, (_, e) => put(renderKatex(e.trim(), true)))
  src = src.replace(/\\\(([\s\S]+?)\\\)/g, (_, e) => put(renderKatex(e.trim(), false)))
  src = src.replace(/\$([^$\n]+?)\$/g, (_, e) => put(renderKatex(e.trim(), false)))
  let html = md.render(src)
  html = html.replace(/zZkatexZz(\d+)zZendZz/g, (_, i) => stash[Number(i)] || '')
  return html
}
