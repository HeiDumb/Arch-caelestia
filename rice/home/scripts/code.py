import re


equation = input("Enter the equation: ").strip()
match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)", equation)

if not match:
    print("Invalid equation. Use a format like 2 + 3.")
    raise SystemExit(1)

primary = float(match.group(1))
operator = match.group(2)
secondary = float(match.group(3))

if operator == "+":
    result = primary + secondary
    label = "sum"
elif operator == "-":
    result = primary - secondary
    label = "difference"
elif operator == "*":
    result = primary * secondary
    label = "product"
else:
    if secondary == 0:
        print("Cannot divide by zero.")
        raise SystemExit(1)

    result = primary / secondary
    label = "division"

print(f"The {label} of the two numbers is: {result}")
