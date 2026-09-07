-- The SQLite audit sandbox fixture: the same three shipped-gold defects and the same two
-- smells as tools/audit-sandbox/fixture.sql, in SQLite.
--
-- Every table, column and row below is written for this sandbox. Nothing is copied from BIRD:
-- what is reproduced is the shape of the three defects the spike found on Mini-Dev (questions
-- 1029, 879 and 207), small enough that a reader can work out both answers by hand. The rows
-- are the PostgreSQL fixture's own rows, so that the two sandboxes measure one set of numbers
-- on two engines and a difference between them is the engine and not the data.
--
-- Loaded by build.py into a file outside the repository. The audit opens that file read-only
-- and writes nothing to it.
--
-- What SQLite cannot express, and what was done about it:
--
--   * Schemas. `CREATE SCHEMA "Quoted"` and the second table called `y` are gone: a SQLite
--     file that has attached nothing holds one schema, `main`, and two tables of one name in
--     two schemas cannot exist in it. Question 900004 goes with them; 900005 stays and names
--     `main.y`, so a qualified name is still measured, resolved and reported as one a shuffled
--     copy does not reach.
--   * Grants. `public.sealed` and question 900003 are gone: a file has no grants, so a table
--     that exists and this login may not read does not arise here. `unreadable_tables` is
--     always empty on this engine and the summary says so.
--   * Single-precision float. SQLite has one floating type, REAL, which is a double, and its
--     `sum()` adds with a compensated summation, so a float total does not change with the
--     order its parts are added in. The `spend` table stays, and question 900001 asks
--     `group_concat` of it instead of `sum`: that is the order-dependent aggregate SQLite does
--     have, and it fires the same probe for the same reason, a result that is a function of
--     the order the rows are stored in rather than of the rows.
--   * Declared types. `bigint` is INTEGER and `text` is TEXT; SQLite keeps the declared text
--     of a column and types the values, so what a column is declared as decides nothing about
--     what its cells come back as.

-- ---------------------------------------------------------------------------------------------
-- q1029: the gold orders ASC where the question asks for the highest speeds.
-- ---------------------------------------------------------------------------------------------

-- The gold returns the four smallest speeds and the correction the four largest, so the two
-- answers are disjoint. Ten teams carry nine distinct speeds and the pair at 50 sits in the
-- middle, where neither the fourth-smallest nor the fourth-largest cut falls: both statements
-- return a stable four rows, and the tie is still in the data one row away from each cut.
CREATE TABLE team (
    id             INTEGER PRIMARY KEY,
    team_api_id    INTEGER NOT NULL UNIQUE,
    team_long_name TEXT    NOT NULL
);

CREATE TABLE team_attributes (
    id               INTEGER PRIMARY KEY,
    team_api_id      INTEGER NOT NULL REFERENCES team (team_api_id),
    buildupplayspeed INTEGER NOT NULL
);

INSERT INTO team (id, team_api_id, team_long_name) VALUES
    (1, 1001, 'Harbour Rovers'),    (2, 1002, 'Quarry Athletic'),
    (3, 1003, 'Lantern City'),      (4, 1004, 'Foundry United'),
    (5, 1005, 'Saltmarsh Town'),    (6, 1006, 'Kiln Wanderers'),
    (7, 1007, 'Beacon Albion'),     (8, 1008, 'Orchard Rangers'),
    (9, 1009, 'Pennine Casuals'),  (10, 1010, 'Weir End');

INSERT INTO team_attributes (id, team_api_id, buildupplayspeed) VALUES
    (1, 1001, 20), (2, 1002, 23), (3, 1003, 31), (4, 1004, 44), (5, 1005, 50),
    (6, 1006, 50), (7, 1007, 62), (8, 1008, 70), (9, 1009, 77), (10, 1010, 80);

-- ---------------------------------------------------------------------------------------------
-- q879: the ordering key is text, so the gold orders numbers as strings.
-- ---------------------------------------------------------------------------------------------

-- fastestlapspeed holds numeric strings in a text column, as the dump does. '93.175' is the
-- largest string and 259.870 the largest number, so the gold's LIMIT 1 lands on one driver and
-- the correction's CAST lands on another, and the two nationalities differ. Two rows hold no
-- speed at all, which SQLite sorts last under DESC without either statement writing it down.
CREATE TABLE drivers (
    driverid    INTEGER PRIMARY KEY,
    driverref   TEXT NOT NULL,
    nationality TEXT NOT NULL
);

CREATE TABLE results (
    resultid        INTEGER PRIMARY KEY,
    raceid          INTEGER NOT NULL,
    driverid        INTEGER NOT NULL REFERENCES drivers (driverid),
    fastestlapspeed TEXT
);

INSERT INTO drivers (driverid, driverref, nationality) VALUES
    (1, 'ahlgren', 'Norwegian'), (2, 'bettencourt', 'Peruvian'),
    (3, 'cardoso',  'Kenyan'),   (4, 'donnelly',    'Icelandic');

INSERT INTO results (resultid, raceid, driverid, fastestlapspeed) VALUES
    (1, 1, 2, '259.870'), (2, 1, 1, '93.175'), (3, 1, 3, '218.300'), (4, 2, 4, '73.450'),
    (5, 2, 2, '241.005'), (6, 2, 1, NULL),     (7, 3, 3, NULL);

-- ---------------------------------------------------------------------------------------------
-- q207: the gold joins an atom to a bond through the molecule instead of through connected.
-- ---------------------------------------------------------------------------------------------

-- Molecule m1 holds one double bond, between the carbon and the oxygen, and a nitrogen that is
-- single-bonded to the carbon. The gold reaches every atom of any molecule that has a double
-- bond anywhere in it and returns three elements; the correction walks atom -> connected -> bond
-- and returns the two that are in the double bond. Molecule m2 has no double bond and neither
-- statement returns its elements, so the difference is the join and not the filter.
CREATE TABLE molecule (
    molecule_id TEXT PRIMARY KEY,
    label       TEXT NOT NULL
);

CREATE TABLE atom (
    atom_id     TEXT PRIMARY KEY,
    molecule_id TEXT NOT NULL REFERENCES molecule (molecule_id),
    element     TEXT NOT NULL
);

CREATE TABLE bond (
    bond_id     TEXT PRIMARY KEY,
    molecule_id TEXT NOT NULL REFERENCES molecule (molecule_id),
    bond_type   TEXT NOT NULL
);

CREATE TABLE connected (
    atom_id  TEXT NOT NULL REFERENCES atom (atom_id),
    atom_id2 TEXT NOT NULL REFERENCES atom (atom_id),
    bond_id  TEXT NOT NULL REFERENCES bond (bond_id),
    PRIMARY KEY (atom_id, atom_id2)
);

INSERT INTO molecule (molecule_id, label) VALUES ('m1', '+'), ('m2', '-');

INSERT INTO atom (atom_id, molecule_id, element) VALUES
    ('m1_1', 'm1', 'c'), ('m1_2', 'm1', 'o'), ('m1_3', 'm1', 'n'),
    ('m2_1', 'm2', 'h'), ('m2_2', 'm2', 's');

INSERT INTO bond (bond_id, molecule_id, bond_type) VALUES
    ('m1_1_2', 'm1', '='), ('m1_1_3', 'm1', '-'), ('m2_1_2', 'm2', '-');

INSERT INTO connected (atom_id, atom_id2, bond_id) VALUES
    ('m1_1', 'm1_2', 'm1_1_2'), ('m1_2', 'm1_1', 'm1_1_2'),
    ('m1_1', 'm1_3', 'm1_1_3'), ('m1_3', 'm1_1', 'm1_1_3'),
    ('m2_1', 'm2_2', 'm2_1_2'), ('m2_2', 'm2_1', 'm2_1_2');

-- ---------------------------------------------------------------------------------------------
-- The two smell tables
-- ---------------------------------------------------------------------------------------------

-- The same fifteen amounts the PostgreSQL fixture holds, in the one floating type SQLite has.
-- What a rerun over a shuffled copy shows here is not a float total that adds up differently:
-- SQLite compensates for that. It is `group_concat`, which writes its parts in whatever order
-- the rows were read in, so the same rows in another physical order give another answer and the
-- probe fires on a result that is a function of the storage order.
CREATE TABLE spend (
    category TEXT,
    spent    REAL
);

INSERT INTO spend (category, spent) VALUES
    ('field', 1000000), ('field', 0.11), ('field', 0.22), ('field', 0.33), ('field', 0.44),
    ('field', 0.55),    ('field', 0.66), ('field', 0.77), ('field', 0.88),
    ('depot', 0.19), ('depot', 0.28), ('depot', 0.37),
    ('yard',  0.46), ('yard',  0.55), ('yard',  0.64);

-- A three-way tie at the top, so `ORDER BY score DESC LIMIT 1` returns one of three names and
-- the engine chooses which. The question that asks for the highest score has three answers here
-- and the gold that bounds it to one has no way to say which of them it meant.
CREATE TABLE scores (
    name  TEXT,
    score INTEGER
);

INSERT INTO scores (name, score) VALUES
    ('ash', 99), ('bram', 99), ('cleo', 99), ('dara', 71), ('esme', 64), ('flint', 12);

-- ---------------------------------------------------------------------------------------------
-- One table a gold names with its schema
-- ---------------------------------------------------------------------------------------------

-- Three decimals as text, which is the first smell's case again under another name. The gold
-- that reads it writes `main.y`, so a qualified name is measured under the schema it named and
-- the shuffled copy the rerun would have read is reported as one the rerun does not reach: an
-- unqualified name finds a TEMP copy first and a qualified one never consults TEMP at all.
-- '10' sorts below '200.5' and both below '9.5', so ordering this mass as a number answers
-- otherwise and the three tags come back in another order.
CREATE TABLE y (
    id  INTEGER PRIMARY KEY,
    tag TEXT NOT NULL,
    mass TEXT NOT NULL
);

INSERT INTO y (id, tag, mass) VALUES
    (1, 'iron', '9.5'), (2, 'lead', '10'), (3, 'zinc', '200.5');
