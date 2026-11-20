with open('app/nlp/validator.py') as f:
    for i, line in enumerate(f, 1):
        if 'invented name' in line.lower() or 'NAME_PATTERN' in line or 'known_names' in line:
            print(f'{i}: {line.rstrip()}')