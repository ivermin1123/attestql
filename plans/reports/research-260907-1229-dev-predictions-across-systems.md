<!-- cspell:ignore ATLAS AlphaSQL AtlasCore CodeS DAIL DAMO GenaSQL GSR LHTB -->
<!-- cspell:ignore Omni RUCKB RSL XiYan birdenv ucdigital Abhi Poluri Graphix UIUC -->
<!-- cspell:ignore dev1106 dev minidev qid sqls fewshot questionmask PTY -->
# Research: BIRD dev predictions across systems

Date 2026-09-08 12:29 +07, tree `a376007fcbe44c7c58e91002d1500460877624b6`. Artifact:
[directory](research-260907-dev-predictions-across-systems/).

## Outcome and assumption

The hunt accepted 21 full-dev files. On the 2024-06-27 gold, 1751 of 18627 credited predictions are
NOT_EQUAL (9.4%), against A37's 10.0%. The pooled denominator counts file rows, not distinct
systems: CodeS contributes 8 configurations and DAIL-SQL 5.

The hand sample is assumed to mean both gold copies: its population is every (file, copy, id) row,
ordered by file, copy and id. Credit movement is reported per file in both directions. No product
file was changed.

## Hunt, licences and pairing

Every accepted URL, commit, sha256, licence and pairing witness is in
[`sources.json`](research-260907-dev-predictions-across-systems/sources.json);
[`prediction-pairing.json`](research-260907-dev-predictions-across-systems/prediction-pairing.json)
holds the machine checks. Accepted groups: Alpha-SQL (MIT), CodeS 8 (Apache-2.0), RSL-SQL two,
DAIL-SQL GPT-4 five, GSR one, CSC-SQL two (all Apache-2.0), and ATLAS Core two (MIT).
The accepted set was fixed at the two-hour mark; 34 further minutes only checked candidate families
while the first PTY run was suspended.

Refused or not usable: OmniSQL, MAC-SQL, E-SQL, TA-SQL, Middleware, hill-climb-RL, AbhiPoluri/sql-r1
and the BIRD-Platinum root have no usable licence for their full outputs; MAG-SQL ships only 24
rows; DTS-SQL and Graphix ship Spider; CHESS is present only as a UIUC 100-question subset;
XiYan-SQL, NL2SQL360, SQL-R1, LHTB, N-rep and ontology2sql exposed no full dev file;
OpenSearch-SQL's bird_dev.json is fewshot source. The DAIL questionmask alias, an Alpha-SQL fork and
a LangSQL CodeS copy are duplicates. One Hugging Face candidate is gated and returns HTTP 401
unauthenticated.

All 21 files have 1534 entries. No accepted file holds an entry with no statement. 12 plain-line
files cannot be read by the tool as shipped; `predictions_readable.py` wraps them, applies DAIL's
own `/*` cut and removes ATLAS's checked tab database suffix. The changed DAIL positions are in
`predictions-readable.json`.

## Measurement

Each file ran once per database and gold copy, 462 SQLite audits, three processes at a time, at the
default statement budget. Every timeout was rerun alone; 115 timeout entries remained. `card_games`
used the byte-identical work copy named by `database-copies.json`, because its WAL sidecars need a
writable directory. The loaded audits stopped at 2026-09-07 22:22 +07 and resumed at 2026-09-08
09:27 +07 without a PTY; a run either finished with a summary before the stall or had every timeout
rerun alone afterward.

|File|C o/n|E1 o/n|B o/n|E0 o/n|ER o/n|CNE o/n|sh o/n|Mo|Mn|TS0 o/n|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|`codes1`|1479/1478|559/535|559/535|975/999|55/56|55/53|9.8%/9.9%|55.0.0.0.0|53.0.0.0.0|55/53|
|`codes1e`|1487/1486|749/693|749/693|785/841|47/48|77/73|10.3%/10.5%|76.1.0.0.0|72.1.0.0.0|76/72|
|`codes3`|1501/1500|643/607|643/607|891/927|33/34|74/76|11.5%/12.5%|72.2.0.0.0|74.1.1.0.0|72/75|
|`codes3e`|1506/1505|822/757|822/757|712/777|28/29|82/80|10.0%/10.6%|81.1.0.0.0|78.1.1.0.0|81/79|
|`codes7`|1514/1513|659/619|659/619|875/915|20/21|72/69|10.9%/11.2%|69.2.1.0.0|67.0.2.0.0|70/69|
|`codes7e`|1513/1512|845/776|845/776|689/758|21/22|89/84|10.5%/10.8%|86.1.2.0.0|82.1.1.0.0|88/83|
|`codes15`|1515/1514|703/663|703/663|831/871|19/20|68/69|9.7%/10.4%|67.0.1.0.0|68.1.0.0.0|68/68|
|`codes15e`|1523/1522|867/802|867/802|667/732|11/12|83/79|9.6%/9.8%|81.1.1.0.0|78.0.1.0.0|82/79|
|`alpha`|1532/1531|1064/1028|1064/1028|470/506|2/3|104/88|9.8%/8.6%|102.0.2.0.0|84.0.4.0.0|104/88|
|`rsl-ds`|1525/1524|980/940|980/940|554/594|9/10|90/88|9.2%/9.4%|89.1.0.0.0|88.0.0.0.0|89/88|
|`rsl-gpt`|1531/1530|1038/982|1038/982|496/552|3/4|101/96|9.7%/9.8%|101.0.0.0.0|95.0.1.0.0|101/96|
|`dail7m80`|1433/1433|820/783|820/783|714/751|101/101|83/87|10.1%/11.1%|81.2.0.0.0|87.0.0.0.0|81/87|
|`dail7m85`|1434/1434|815/781|815/781|719/753|100/100|84/84|10.3%/10.8%|82.2.0.0.0|84.0.0.0.0|82/84|
|`dail7q`|1431/1431|814/778|814/778|720/756|103/103|77/77|9.5%/9.9%|76.1.0.0.0|77.0.0.0.0|76/77|
|`dail9m`|1436/1436|821/780|821/780|713/754|98/98|81/88|9.9%/11.3%|79.2.0.0.0|87.1.0.0.0|80/88|
|`dail9q`|1436/1436|814/773|814/773|720/761|98/98|77/79|9.5%/10.2%|76.1.0.0.0|79.0.0.0.0|76/79|
|`gsr`|1526/1525|1020/971|1020/971|514/563|8/9|108/105|10.6%/10.8%|90.18.0.0.0|86.19.0.0.0|91/87|
|`csc7`|1530/1529|1061/984|1061/984|473/550|4/5|104/108|9.8%/11.0%|101.2.1.0.0|105.1.2.0.0|102/107|
|`csc32`|1532/1531|1094/1032|1094/1032|440/502|2/3|95/96|8.7%/9.3%|93.1.1.0.0|94.0.2.0.0|94/96|
|`atlas1`|1529/1529|1214/1109|1214/1109|320/425|5/5|74/64|6.1%/5.8%|70.2.2.0.0|61.0.3.0.0|72/64|
|`atlas2`|1530/1529|1225/1113|1225/1112|309/421|4/5|73/60|6.0%/5.4%|70.1.2.0.0|57.0.3.0.0|72/60|

C is compared, E1 is the tool's BIRD EX, B is BIRD's own score, E0 is EX=0, ER is ERROR, and CNE
means credited by BIRD but NOT_EQUAL; sh is CNE share, o/n is old gold over 2025-11-06. Each M
multiplicity.type.order.truncation.other, and TS0 is the test-suite reading refusing that CNE row.

The tool's BIRD EX reading and BIRD's unmodified evaluator agree on 64427 of 64428 readable rows
across all file-copy pairs. Per-file official sums, errors, timeouts and every disagreement row are
in `prediction-measurement.json`; there were 1 disagreements.
The one disagreement is `atlas2` q1126 on the new gold: the tool says EQUAL and BIRD's evaluator
times out.
Pooled ERROR sides are prediction 1424, gold 105, run 28; steps are execute 1437, statement 92,
row-count 28.

## Credits moved by the gold

Of 399 rewritten golds, 2001 old credits were lost and 880 were gained, 2881 movements over 21
files. Per-file movements range 70 to 203; every moved id and its rewritten-gold overlap is in
`credits-moved.json`.

## Hand sample

Rule: all EX=1 and NOT_EQUAL rows ordered by (file, copy, id), every 69th row, first 50. Classes: A
wrong answer BIRD credited, B harmless, C typed rule alone. The sample found 0 A, 49 B and 1 C; A is
0.0% and A or B is 98.0%.

|File|Copy|Q|C|Reason|File|Copy|Q|C|Reason|
|---|---|---:|---|---|---|---|---:|---|---|
|`alpha`|dev1106|101|B|Same distinct values.|`alpha`|dev1106|1212|B|Same distinct values.|
|`alpha`|old|845|B|Same distinct values.|`atlas1`|dev1106|473|B|Same distinct values.|
|`atlas1`|old|483|B|Same distinct values.|`atlas2`|dev1106|407|B|Same distinct values.|
|`atlas2`|old|521|B|Same distinct values.|`csc32`|dev1106|452|B|Same distinct values.|
|`csc32`|dev1106|1447|B|Same distinct values.|`csc32`|old|1088|B|Same distinct values.|
|`csc7`|dev1106|481|B|Same distinct values.|`csc7`|dev1106|1503|B|Same distinct values.|
|`csc7`|old|1059|B|Same distinct values.|`dail7m80`|dev1106|452|B|Same distinct values.|
|`dail7m80`|old|275|B|Same distinct values.|`dail7m80`|old|1514|B|Same distinct values.|
|`dail7m85`|dev1106|1220|B|Same distinct values.|`dail7m85`|old|1066|B|Same distinct values.|
|`dail7q`|dev1106|854|B|Same distinct values.|`dail7q`|old|681|B|Same distinct values.|
|`dail9m`|dev1106|407|B|Same distinct values.|`dail9m`|old|206|B|Same distinct values.|
|`dail9m`|old|1435|B|Same distinct values.|`dail9q`|dev1106|1214|B|Same distinct values.|
|`dail9q`|old|1071|B|Same distinct values.|`gsr`|dev1106|610|B|Same distinct values.|
|`gsr`|old|229|B|Same distinct values.|`gsr`|old|1071|B|Same distinct values.|
|`codes15e`|dev1106|868|B|Same distinct values.|`codes15e`|old|522|B|Same distinct values.|
|`codes15`|dev1106|355|B|Same distinct values.|`codes15`|old|321|B|Same distinct values.|
|`codes1e`|dev1106|449|B|Same distinct values.|`codes1e`|old|355|B|Same distinct values.|
|`codes1`|dev1106|316|B|Same distinct values.|`codes1`|old|635|B|Same distinct values.|
|`codes3e`|dev1106|758|B|Same distinct values.|`codes3e`|old|390|B|Same distinct values.|
|`codes3`|dev1106|257|B|Same distinct values.|`codes3`|old|44|C|Storage class only.|
|`codes3`|old|1449|B|Same distinct values.|`codes7e`|dev1106|1209|B|Same distinct values.|
|`codes7e`|old|1054|B|Same distinct values.|`codes7`|dev1106|622|B|Same distinct values.|
|`codes7`|old|521|B|Same distinct values.|`rsl-ds`|dev1106|452|B|Same distinct values.|
|`rsl-ds`|old|258|B|Same distinct values.|`rsl-ds`|old|1244|B|Same distinct values.|
|`rsl-gpt`|dev1106|1051|B|Same distinct values.|`rsl-gpt`|old|470|B|Same distinct values.|

## Unresolved questions

- Whether BIRD-Platinum's unlicensed full OmniSQL output can be replaced by an upstream file under a
    clear licence.
- Whether ATLAS Core's two runs use the same unnamed model; the shipped run directories do not state
    it.
- Whether the 12 plain-line wrappers belong in AttestQL or should stay a measurement-side adapter.

## What changes in AttestQL

Add to register row A37: the pooled old-gold 1751/18627 (9.4%), the per-file and per-copy rows in
`prediction-measurement.json`, the exact BIRD agreement count, the movement totals, and the sample's
A/B/C counts. Name the 12 unread-as-shipped plain-line files as a parser/input gap; the selected
JSON files themselves need no change.
