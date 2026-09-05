DROP TABLE IF EXISTS collation_demo;
CREATE TABLE collation_demo (v text);
INSERT INTO collation_demo (v) VALUES ('apple'), ('Apple'), ('Banana'), ('banana'), ('Zebra'), ('able');
