<!-- cspell:ignore ATLAS AlphaSQL AtlasCore CodeS DAIL DAMO GenaSQL GSR LHTB -->
<!-- cspell:ignore Omni RUCKB RSL XiYan birdenv ucdigital Abhi Poluri Graphix UIUC -->
<!-- cspell:ignore dev1106 dev minidev qid sqls fewshot questionmask PTY azorius Takr -->
# Research: BIRD dev predictions across systems

Date 2026-09-08 12:49 +07, tree `c109d4637fcea989c3647072cf50ae590121b8e2`. Artifact:
[directory](research-260907-dev-predictions-across-systems/).

## Outcome and assumption

The hunt accepted 21 full-dev files. On the 2024-06-27 gold, 1751 of 18627 credited predictions are
NOT_EQUAL (9.4%), against A37's 10.0%. The pooled denominator counts file rows, not distinct
systems: CodeS contributes 8 configurations and DAIL-SQL 5. In the hand-read sample of 50
credited-but-NOT_EQUAL rows, 18 are wrong answers the benchmark credited (36.0%).

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
in `prediction-measurement.json`, which is 11.1 MB and left the tree on 2026-09-11 for the
asset `research-260907-dev-predictions-across-systems.tar.gz` of the `v0.3.0` release (sha256
`38a66be0…`, and `d3ed69e7…` for the file inside it); there was 1 disagreement.
The one disagreement is `atlas2` q1126 on the new gold: the tool says EQUAL and BIRD's evaluator
times out.
Pooled ERROR sides are prediction 1424, gold 105, run 28; steps are execute 1437, statement 92,
row-count 28.

## Credits moved by the gold

Of 399 rewritten golds, 2001 old credits were lost and 880 were gained, 2881 movements over 21
files. Per-file movements range 70 to 203; every moved id and its rewritten-gold overlap is in
`credits-moved.json`.

## Hand sample

Selection: all EX=1 and NOT_EQUAL rows ordered by (file, copy, id), every 69th row, first 50;
population 3454. Each row was read by hand from the question, both statements, both results and the
tool's differing-row summary; q635 and q44 were also checked in the database. A is a wrong answer
the benchmark credited: a different question answered, a scalar repeated per row of an unrelated
table, or the things asked for (names, ids, patients, events) listed at least twice over. B is
harmless: one distinct row repeated, DISTINCT added to the gold's answer, or a list under twice the
answer's length with every row present. C is the tool's rule alone: the same value under another
declared type or storage class. The twice line is applied as written, so 2.2x and 2.35x rows (q1220,
q758, q1447) are A.

The sample found 18 A, 31 B and 1 C; A is 36.0% and A or B is 98.0%. A first pass classed 49 rows B
by template; this row-by-row reading replaced it on 2026-09-08. The 19 A and C rows:

|File|Copy|Q|Gold|Pred|Pred distinct|C|Reason|
|---|---|---:|---:|---:|---:|---|---|
|`csc32`|dev1106|452|21738|56707|21738|A|Cards with a text box: 21,738 distinct names, prediction 56,707 rows (Forest 691x); 2.6x, asks for names.|
|`csc32`|dev1106|1447|20|47|20|A|Events that underspend: 20 distinct (name, location), prediction 47 rows, one per budget line; 2.35x.|
|`csc32`|old|1088|1105|15429|1105|A|Players with volleys and dribbling over 70: 1,105 distinct names, prediction 15,429 rows per snapshot; 14x.|
|`csc7`|dev1106|1503|7|66|7|A|Products bought in EUR: 7 distinct descriptions, prediction 66 rows (Diesel 41x), one per transaction; 9x.|
|`csc7`|old|1059|7258|120895|7165|A|Players taller than 180: gold 7,258 names (7,165 distinct), prediction joins attributes, 120,895 rows; 17x.|
|`dail7m80`|dev1106|452|21738|56707|21738|A|Cards with a text box: 21,738 distinct names, prediction 56,707 rows (Forest 691x); 2.6x, asks for names.|
|`dail7m80`|old|275|370|1844|370|A|Molecules with a double bond: 370 distinct ids, prediction 1,844 rows, one per bond (TR397 26x); 5x.|
|`dail7m85`|dev1106|1220|20|44|20|A|Patients with UN = 29: 20 distinct (ID, sex, birthday), prediction 44 rows, one per lab test; 2.2x.|
|`dail9q`|dev1106|1214|68|544|68|A|Patients with TP below 6: 68 distinct (ID, sex, birthday), prediction 544 rows, one per lab test; 8x.|
|`gsr`|dev1106|610|80|456|80|A|Badges of the top-reputation user: 80 distinct names, prediction 456 rows (Nice Answer 205x); 5.7x.|
|`codes15e`|old|522|2|66|2|A|EDHRec rank-1 cards and banned formats: gold 2 grouped (Sol Ring, format) rows, prediction 66, each 33x.|
|`codes1e`|dev1106|449|250|1035|250|A|Language and type of azorius cards: 250 distinct pairs, prediction 1,035 rows, one per translation; 4x.|
|`codes1`|dev1106|316|189|2000|189|A|Non-carcinogenic molecules with c: 189 distinct ids, prediction 2,000 rows, one per carbon atom; 10x.|
|`codes1`|old|635|12|1|1|A|Posts by Matt Parker with over 4 votes: prediction counts his 5 bounty votes with BountyAmount > 4 instead.|
|`codes3e`|dev1106|758|5|11|5|A|Hair colour of 185 cm human heroes: 5 distinct colours, prediction 11 rows, one per hero; 2.2x, at threshold.|
|`codes3`|old|44|1|1|1|C|One row (435, Los Angeles) both sides; INTEGER 435 vs AVG() REAL 435.0; NumTstTakr picks the same record.|
|`codes3`|old|1449|2|6|2|A|Members with an expense over 100: 2 distinct (name, major) rows, prediction 6, each member 3 times; 3x.|
|`codes7e`|dev1106|1209|38|871|38|A|Diagnoses with GPT > 60: 38 distinct, prediction 871 rows (SLE 281x) per lab test, ordered DESC not ASC; 23x.|
|`rsl-ds`|dev1106|452|21738|56707|21738|A|Cards with a text box: 21,738 distinct names, prediction 56,707 rows (Forest 691x); 2.6x, asks for names.|

The 31 B rows (reasons in `classification.json`): `alpha` dev1106 q101, q1212, old q845; `atlas1`
dev1106 q473, old q483; `atlas2` dev1106 q407, old q521; `csc7` dev1106 q481; `dail7m80` old q1514;
`dail7m85` old q1066; `dail7q` dev1106 q854, old q681; `dail9m` dev1106 q407, old q206, q1435;
`dail9q` old q1071; `gsr` old q229, q1071; `codes15e` dev1106 q868; `codes15` dev1106 q355, old
q321; `codes1e` old q355; `codes3e` old q390; `codes3` dev1106 q257; `codes7e` old q1054; `codes7`
dev1106 q622, old q521; `rsl-ds` old q258, q1244; `rsl-gpt` dev1106 q1051, old q470.

## Unresolved questions

- Whether a clearly licensed upstream file can replace BIRD-Platinum's unlicensed OmniSQL output.
- Whether ATLAS Core's two runs use the same unnamed model; the run directories do not say.
- Whether the 12 plain-line wrappers belong in AttestQL or stay a measurement-side adapter.

## What changes in AttestQL

Add to register row A37: the pooled old-gold 1751/18627 (9.4%), the per-file and per-copy rows in
`prediction-measurement.json` (now the release asset named above), the exact BIRD agreement count, the movement totals, and the sample's
A/B/C counts. Name the 12 unread-as-shipped plain-line files as a parser/input gap; the selected
JSON files themselves need no change.
