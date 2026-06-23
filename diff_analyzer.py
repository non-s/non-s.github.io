import re

patch_path = '.agents/auditor_gen2/unstaged_diff.patch'

def analyze_patch():
    # Try UTF-16 first because of Windows PowerShell redirect
    try:
        with open(patch_path, 'r', encoding='utf-16') as f:
            content = f.read()
    except Exception:
        with open(patch_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

    files = re.split(r'^diff --git ', content, flags=re.MULTILINE)
    print(f"Total files in diff: {len(files) - 1}")

    for file_diff in files[1:]:
        lines = file_diff.splitlines()
        header = lines[0]
        print(f"\n--- FILE: {header} ---")
        
        added_lines = [l for l in lines if l.startswith('+') and not l.startswith('+++')]
        deleted_lines = [l for l in lines if l.startswith('-') and not l.startswith('---')]
        
        print(f"Added lines: {len(added_lines)}, Deleted lines: {len(deleted_lines)}")
        
        suspicious = []
        for l in added_lines:
            text = l[1:].strip()
            # Look for typical mock/bypass/fake/hardcoded results patterns
            if any(p in text.lower() for p in ['mock', 'bypass', 'fake', 'stub', 'return true', 'return false', 'return "en"', "return 'en'", 'hardcode', 'assert']):
                suspicious.append(text)
                
        if suspicious:
            print(f"Found {len(suspicious)} suspicious mock/bypass/assert lines:")
            for s in suspicious[:15]:
                print(f"  {s}")

if __name__ == '__main__':
    analyze_patch()
