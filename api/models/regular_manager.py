import re

def validate_username(username):
    # 正则表达式：允许邮箱地址、字母或数字
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'  # 邮箱格式
    alphanumeric_pattern = r'^[a-zA-Z]+[0-9]*$|^[0-9]+$'  # 允许字母、数字以及字母加数字(字母必须在前)

    # 判断用户名是否符合邮箱格式或字母数字格式
    if re.match(email_pattern, username) or re.match(alphanumeric_pattern, username):
        return True
    else:
        return False