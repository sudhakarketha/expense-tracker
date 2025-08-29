from expenses.add_expense import add_expense
from expenses.display_month import display_current_month_expenses

def main():
    while True:
        print("Expense Tracker")
        print("1. Add Expense")
        print("2. Display Current Month Expenses")
        print("3. Exit")
        
        choice = input("Choose an option: ")
        
        if choice == '1':
            amount = float(input("Enter expense amount: "))
            description = input("Enter expense description: ")
            add_expense(amount, description)
            print("Expense added successfully.")
        
        elif choice == '2':
            display_current_month_expenses()
        
        elif choice == '3':
            print("Exiting the application.")
            break
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()