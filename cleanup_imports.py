import os
import re

def fix_doubles(content):
    # Regex to find and fix "from emile.X from emile.X import Y"
    content = re.sub(r'from emile\.(core|backtests) from emile\.\1 import', r'from emile.\1 import', content)
    # Regex to find and fix "from emile.X from emile.X as X"
    content = re.sub(r'import emile\.(core|backtests)\.(\w+) as emile\.\1\.\2', r'from emile.\1 import \2', content)
    return content

for folder in ["emile", "tests"]:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()
                updated = fix_doubles(content)
                if updated != content:
                    with open(path, "w") as f:
                        f.write(updated)
                    print(f"Fixed double imports in: {path}")

print("Clean up complete.")
