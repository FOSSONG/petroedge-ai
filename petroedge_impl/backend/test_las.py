from app.services.las_parser import parse_las

rows = parse_las(
    "data/mywell.las",
    max_records=5
)

for row in rows:
    print(row)