import ast, sys, os
roots = sys.argv[1:]
seen = {}
stack = list(roots)
while stack:
    f = stack.pop()
    if f in seen: continue
    src = open(f).read()
    t = ast.parse(src)
    deps = set()
    for n in ast.walk(t):
        mods = []
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods = [n.module]
        for m in mods:
            p = os.path.join('tools', m.replace('.', '/') + '.py')
            if os.path.exists(p): deps.add(p)
            p2 = os.path.join('tools', m.replace('.', '/'), '__init__.py')
            if os.path.exists(p2): deps.add(p2)
    seen[f] = sorted(deps)
    stack.extend(deps)
for f in sorted(seen):
    print(f, '->', ' '.join(seen[f]))
