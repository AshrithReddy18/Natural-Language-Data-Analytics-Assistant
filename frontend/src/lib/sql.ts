// A small SQL tokenizer for syntax highlighting. It only colours text; it never interprets SQL.

export type TokenType = 'keyword' | 'function' | 'string' | 'number' | 'comment' | 'operator' | 'identifier' | 'space'
export interface Token {
  type: TokenType
  text: string
}

const KEYWORDS = new Set(
  `select from where and or not in is null as on join left right inner outer full cross group by order having
  limit offset distinct union all intersect except with recursive case when then else end asc desc between like
  ilike exists interval true false over partition rows range preceding following current row filter within
  using natural lateral cast date timestamp any some nulls first last`
    .split(/\s+/)
    .filter(Boolean),
)

const PATTERNS: [TokenType, RegExp][] = [
  ['space', /^\s+/],
  ['comment', /^(--[^\n]*|\/\*[\s\S]*?(\*\/|$))/],
  ['string', /^'(?:[^']|'')*'?/],
  ['identifier', /^"(?:[^"]|"")*"?/],
  ['number', /^\d+(\.\d+)?/],
  ['identifier', /^[A-Za-z_][A-Za-z0-9_$]*/],
  ['operator', /^(::|<=|>=|<>|!=|\|\||[-+*/%=<>(),.;])/],
]

export function tokenizeSql(sql: string): Token[] {
  const tokens: Token[] = []
  let rest = sql
  while (rest.length) {
    let matched = false
    for (const [type, re] of PATTERNS) {
      const m = re.exec(rest)
      if (!m) continue
      const text = m[0]
      let t: TokenType = type
      if (type === 'identifier' && /^[A-Za-z_]/.test(text)) {
        if (KEYWORDS.has(text.toLowerCase())) t = 'keyword'
        else if (/^\s*\(/.test(rest.slice(text.length))) t = 'function'
      }
      tokens.push({ type: t, text })
      rest = rest.slice(text.length)
      matched = true
      break
    }
    if (!matched) {
      tokens.push({ type: 'operator', text: rest[0] })
      rest = rest.slice(1)
    }
  }
  return tokens
}

/** Split tokens into lines (for line numbers), splitting multi-line tokens as needed. */
export function tokenLines(sql: string): Token[][] {
  const lines: Token[][] = [[]]
  for (const token of tokenizeSql(sql)) {
    const parts = token.text.split('\n')
    parts.forEach((part, i) => {
      if (i > 0) lines.push([])
      if (part) lines[lines.length - 1].push({ type: token.type, text: part })
    })
  }
  return lines
}

export function normalizeSql(sql: string): string {
  return sql.replace(/\s+/g, ' ').replace(/;\s*$/, '').trim().toLowerCase()
}
