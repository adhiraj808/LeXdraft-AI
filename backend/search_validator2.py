with open('app/nlp/validator.py') as f:
    lines = f.readlines()

results = []
for i, line in enumerate(lines, 1):
    if 'invented name' in line.lower() or 'NAME_PATTERN' in line or 'known_names' in line:
        results.append(f'{i}: {line.rstrip()}')

with open('search_results.txt', 'w') as f:
    for r in results:
        f.write(r + '\n')