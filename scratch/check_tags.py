
import re

def check_balance(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all template tags
    tags = re.findall(r'{%\s*(if|else|elif|endif|for|empty|endfor|block|endblock)\s*.*?%}', content)
    
    stack = []
    errors = []
    
    for tag in tags:
        if tag == 'if':
            stack.append(('if', tag))
        elif tag == 'for':
            stack.append(('for', tag))
        elif tag == 'block':
            stack.append(('block', tag))
        elif tag == 'endif':
            if not stack or stack[-1][0] != 'if':
                errors.append(f"Unbalanced endif: stack is {stack}")
            else:
                stack.pop()
        elif tag == 'endfor':
            if not stack or stack[-1][0] != 'for':
                errors.append(f"Unbalanced endfor: stack is {stack}")
            else:
                stack.pop()
        elif tag == 'endblock':
            if not stack or stack[-1][0] != 'block':
                errors.append(f"Unbalanced endblock: stack is {stack}")
            else:
                stack.pop()
    
    return stack, errors

stack, errors = check_balance('templates/seo/workspace_seo.html')
print(f"Remaining stack: {stack}")
print(f"Errors: {errors}")
