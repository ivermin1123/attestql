# sqlglot's SQLite dialect: what it reads, and the one thing it reads differently

Written 2026-09-05 by the worker dispatched for the SQLite backend and parser, which stopped
before writing any code when the owner's directive of 11:29 halted Batch B where it stood. The
tree is clean and nothing was committed. What is here is the reading of the parser that the
halted work had already done, so that whoever resumes does not pay for it twice.

## What was verified about the candidate parser

`sqlglot` 30.18.0 on PyPI: licence expression MIT, no runtime dependency of its own (every
`requires_dist` entry is behind the `dev`, `c` or `rs` extra), `requires-python >=3.9`. It
installs and imports under this project's locked environment. It was added to `pyproject.toml`
and `uv.lock` during the halted work and both files have been restored; re-adding it is one
pinned line and a `uv sync`.

The SQLite dialect reads every shape the audit asks about, and round-trips them back as SQLite:
a top-level `ORDER BY` with direction and an explicit `NULLS FIRST`/`NULLS LAST`, a constant
`LIMIT` and `OFFSET`, `DISTINCT`, set operations, common table expressions, a subquery in
`FROM`, table aliases, `CAST(x AS REAL)`, `IIF` and `strftime`. Two normalisations happen on
the way back out and are worth knowing before a rewrite is compared with the text it came
from: `LIMIT 3, 2` is written back as `LIMIT 2 OFFSET 3`, and a backtick-quoted identifier is
written back double-quoted (`` `col` `` becomes `"col"`).

## The trap of ADR-0014, point 4 of Context, as measured

The ADR expects sqlglot's SQLite dialect to read a double-quoted token and a backtick token the
way SQLite does. It reads the backtick correctly: `` `col` `` is an identifier. It does **not**
read the double-quoted token the way SQLite does, and it cannot.

SQLite's rule is resolved against the schema at prepare time: a double-quoted token is an
identifier where it resolves to one, and falls back to a string literal where it does not and
where a string literal is allowed. sqlglot has no schema, so it reads a double-quoted token as
an identifier in every position:

```text
SELECT * FROM t WHERE a = "some string"
  ->  EQ(Column(a), Column(Identifier('some string', quoted=True)))
```

SQLite executing that statement compares `a` with the string `some string` whenever no column
of that name is in scope. sqlglot calls it a column.

Two consequences for whoever writes the parser:

- The parse tree does not record which quote character was used, so a check cannot tell a
  backtick identifier from a double-quoted one off the tree alone. The tokenizer does: its
  tokens carry `start` and `end` offsets into the original text, so `sql[token.start]` is the
  quote character, and an `IDENTIFIER` token opened with `"` is the ambiguous one.
- The ambiguity is confined to a **bare** double-quoted name in expression position. A
  double-quoted table name, a double-quoted alias and a qualified `t."col"` are unambiguous,
  because SQLite allows no string literal in any of those places.

What the halted work was about to implement, from the phase spec ("if sqlglot gets one of them
wrong, refuse the statement with a reason rather than reading it silently"): refuse a statement
carrying a bare double-quoted name in expression position, naming the token and the rule.

**The consequence that needs a decision before that is written.** BIRD's SQLite golds routinely
double-quote a real column name that holds spaces or punctuation, for example
`SELECT "Free Meal Count (K-12)" FROM schools ORDER BY "Free Meal Count (K-12)" DESC LIMIT 1`.
Those are correct statements that the refusal above would reject, so the refusal costs a share
of BIRD dev that nobody has counted yet. R-D's finding that sqlglot 30.18.0 parses 100 % of the
BIRD dev and Mini-Dev SQLite golds is about parsing and does not speak to this: the statements
parse, they are only read with a different meaning where the token is not a column.

The audit's own exposure to the wrong reading is small, which is what makes a blanket refusal
look expensive rather than safe. A double-quoted string literal never becomes a table name, so
the fixture measurement is unaffected; it never becomes an `output_names` entry, since those
are explicit aliases only; and both statement rewrites keep the token verbatim, so an executed
variant still means to SQLite what the gold meant. The one place a wrong reading reaches an
answer is a top-level `ORDER BY` key that is a bare double-quoted literal, where the parse
would state a sort key over a column that does not exist; the numeric-text smell already
reports that key as resolving to no column of the FROM clause and stays quiet.

Three options, for whoever owns the decision:

1. Refuse every bare double-quoted name in expression position. Literal compliance with the
   phase spec, conservative in the direction this codebase always chooses, and it rejects
   correct BIRD golds.
2. Refuse only where the audit would otherwise state a fact it cannot support: a top-level
   `ORDER BY` key that is a bare double-quoted name. Keeps the projection and the `WHERE`
   clause, which the audit reads nothing off, and covers the one path to a wrong answer.
3. Resolve the token against the schema the backend already holds, and refuse only what the
   schema says is not a column. This is what SQLite itself does, and it breaks the rule in
   `audit/parse.py` that a parse reaches no database.

## Unresolved

- Which of the three options above the SQLite parser is written under.
- How many BIRD dev golds option 1 would refuse. Not measured; it needs the gold files R-D
  already has open.
