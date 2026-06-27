import re

with open(r'C:\侧耳倾听\src\ai_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the参会人员 section using a more robust approach
# First, find the line numbers
lines = content.split('\n')
start_line = None
end_line = None
for i, line in enumerate(lines):
    if '### 参会人员' in line:
        start_line = i
    if start_line and '### 讨论要点' in line:
        end_line = i
        break

if start_line and end_line:
    # Rebuild the参会人员 section
    new_section = [
        '            "### 参会人员\\n"',
        '            "列出所有参会人员，每人一行。\\n\\n"',
        '            "规则：\\n"',
        '            "- 如果该说话人已被音色库识别（见下方\\u201c已识别的说话人\\u201d），"',
        '            "直接使用该姓名，格式为 `[Speaker N] 姓名`，不要添加任何角色推断\\n"',
        '            "- 如果转写内容中显示该说话人的真实姓名（如自我介绍、称呼），"',
        '            "直接使用该姓名，格式为 `[Speaker N] 姓名`\\n"',
        '            "- 只有在完全无法确定姓名时，才根据发言内容推断角色，"',
        '            "格式为 `[Speaker N]（角色推断：XXX）`\\n"',
        '            "- 【禁止】使用\\u201c未识别姓名\\u201d、\\u201c未知\\u201d、\\u201cUnknown\\u201d等占位符\\n\\n"',
    ]
    
    # Replace lines
    lines = lines[:start_line] + new_section + lines[end_line:]
    
    with open(r'C:\侧耳倾听\src\ai_service.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f'Replaced lines {start_line+1} to {end_line}')
else:
    print(f'Could not find section: start={start_line}, end={end_line}')
