# Expense Tracker

This is a simple expense tracker application that allows users to add daily expenses and view their expenses for the current month. 

## Features

- Add daily expenses with a description and amount.
- Display all expenses for the current month.

## Project Structure

```
expense-tracker
├── src
│   ├── main.py               # Entry point of the application
│   ├── expenses
│   │   ├── add_expense.py    # Functionality to add expenses
│   │   └── display_month.py   # Functionality to display current month expenses
│   └── utils
│       └── date_utils.py     # Utility functions for date operations
├── requirements.txt          # Project dependencies
└── README.md                 # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd expense-tracker
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command:
```
python src/main.py
```

Follow the on-screen instructions to add expenses and view current month expenses. 

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes. 

## License

This project is open source and available under the MIT License.