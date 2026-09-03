-- The audit sandbox fixture: three shipped-gold defects and two smells, in synthetic rows.
--
-- Every table, column and row below is written for this sandbox. Nothing is copied from BIRD:
-- what is reproduced is the shape of the three defects the spike found on the Mini-Dev
-- PostgreSQL dump (questions 1029, 879 and 207), small enough that a reader can work out both
-- answers by hand and see why they differ. The identifiers are lowercase because the dump's are
-- and because the gold statements name their tables unquoted, which the server folds to
-- lowercase anyway.
--
-- Loaded by run.sh as the container superuser into the database `audit`, before the read-only
-- `auditor` login is created and granted SELECT, so nothing here names a role or a credential.

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------------------------
-- q1029: the gold orders ASC NULLS FIRST where the question asks for the highest speeds.
-- ---------------------------------------------------------------------------------------------

-- The gold returns the four smallest speeds and the correction the four largest, so the two
-- answers are disjoint. Ten teams carry nine distinct speeds and the pair at 50 sits in the
-- middle, where neither the fourth-smallest nor the fourth-largest cut falls: both statements
-- return a stable four rows, and the tie is still in the data one row away from each cut.
CREATE TABLE team (
    id             bigint PRIMARY KEY,
    team_api_id    bigint NOT NULL UNIQUE,
    team_long_name text   NOT NULL
);

CREATE TABLE team_attributes (
    id               bigint PRIMARY KEY,
    team_api_id      bigint NOT NULL REFERENCES team (team_api_id),
    buildupplayspeed bigint NOT NULL
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
-- the correction's cast lands on another, and the two nationalities differ. Two rows hold no
-- speed at all, which is what NULLS LAST in both statements is there for.
CREATE TABLE drivers (
    driverid    bigint PRIMARY KEY,
    driverref   text   NOT NULL,
    nationality text   NOT NULL
);

CREATE TABLE results (
    resultid        bigint PRIMARY KEY,
    raceid          bigint NOT NULL,
    driverid        bigint NOT NULL REFERENCES drivers (driverid),
    fastestlapspeed text
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
    molecule_id text PRIMARY KEY,
    label       text NOT NULL
);

CREATE TABLE atom (
    atom_id     text PRIMARY KEY,
    molecule_id text NOT NULL REFERENCES molecule (molecule_id),
    element     text NOT NULL
);

CREATE TABLE bond (
    bond_id     text PRIMARY KEY,
    molecule_id text NOT NULL REFERENCES molecule (molecule_id),
    bond_type   text NOT NULL
);

CREATE TABLE connected (
    atom_id  text NOT NULL REFERENCES atom (atom_id),
    atom_id2 text NOT NULL REFERENCES atom (atom_id),
    bond_id  text NOT NULL REFERENCES bond (bond_id),
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

-- Single-precision money, which no sum can add associatively: float4 holds seven digits, so the
-- large purchase in field and the eight small amounts after it total one way when it is added
-- first and another when it is added last, which is what a rerun over a shuffled copy shows.
CREATE TABLE spend (
    category text,
    spent    float4
);

INSERT INTO spend (category, spent) VALUES
    ('field', 1000000), ('field', 0.11), ('field', 0.22), ('field', 0.33), ('field', 0.44),
    ('field', 0.55),    ('field', 0.66), ('field', 0.77), ('field', 0.88),
    ('depot', 0.19), ('depot', 0.28), ('depot', 0.37),
    ('yard',  0.46), ('yard',  0.55), ('yard',  0.64);

-- A three-way tie at the top, so `ORDER BY score DESC LIMIT 1` returns one of three names and
-- the server chooses which. The question that asks for the highest score has three answers here
-- and the gold that bounds it to one has no way to say which of them it meant.
CREATE TABLE scores (
    name  text,
    score integer
);

INSERT INTO scores (name, score) VALUES
    ('ash', 99), ('bram', 99), ('cleo', 99), ('dara', 71), ('esme', 64), ('flint', 12);
