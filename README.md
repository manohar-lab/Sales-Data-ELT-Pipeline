# Sales Data ELT Pipeline

A beginner-friendly Data Engineering project that demonstrates how to extract sales data from CSV files, load raw data into SQLite, transform data using SQL, and generate meaningful business insights through an interactive dashboard.

## 1. Project Overview

Businesses generate sales data every day. However, raw sales records are not always ready for analysis because they may contain duplicate entries, inconsistent values, or unorganized information.

This project aims to build a simple, modular ELT pipeline that organizes raw sales data into a structured database and prepares it for business analysis.

The project will be developed incrementally in six phases, with each phase tested before moving to the next.

## 2. Project Objectives

- Read sales records from CSV files.
- Load raw sales data into an SQLite database.
- Transform and clean data using SQL.
- Generate useful sales analytics.
- Build an interactive dashboard.
- Validate the pipeline and prepare it for deployment.

## 3. Technology Stack

| Technology     | Purpose                             |
| -------------- | ----------------------------------- |
| Python         | Pipeline implementation             |
| Pandas         | CSV handling and data inspection    |
| CSV            | Initial raw data source             |
| SQLite         | Database for storing sales records  |
| SQL            | Data cleaning and transformation    |
| Streamlit      | Interactive analytics dashboard     |
| Plotly         | Interactive visualizations          |
| Git and GitHub | Version control and project hosting |

## 4. ELT Architecture

The planned pipeline follows these steps:

```text
          Raw Sales Dataset
               CSV File
                  |
                  v
             EXTRACTION
         Read source records
                  |
                  v
                LOADING
       Store raw data in SQLite
                  |
                  v
             TRANSFORMATION
        Clean and aggregate data
             using SQL
                  |
                  v
          Analytical Data
                  |
                  v
           STREAMLIT DASHBOARD
          Charts and KPIs
```

**Why ELT?**

ELT stands for Extract, Load, Transform. Unlike traditional ETL, where transformation happens before loading, this project loads the raw records into the database first and performs the main transformations afterward.

## 5. Dataset Description

The project will use a sample sales dataset stored in `data/sales.csv`.

| Column           | Description                   |
| ---------------- | ----------------------------- |
| `order_id`       | Unique order identifier       |
| `order_date`     | Date of the order             |
| `customer_id`    | Customer identifier           |
| `product_name`   | Name of the purchased product |
| `category`       | Product category              |
| `quantity`       | Number of units purchased     |
| `unit_price`     | Price per unit                |
| `city`           | Customer's city               |
| `payment_method` | Payment method used           |

The initial dataset will contain at least 100 realistic sample records.

## 6. Planned Analytics

Once the pipeline is implemented, the dashboard will display:

- Total sales revenue
- Total number of orders
- Total units sold
- Best-selling products
- City-wise sales performance
- Monthly revenue trends
- Product category performance

These metrics will be calculated from the processed database records.

## 7. Project Folder Structure

The planned modular structure is:

```text
sales-elt-pipeline/
│
├── data/
│   └── sales.csv
│
├── src/
│   └── __init__.py
│
├── dashboard/
│   └── .gitkeep
│
├── sql/
│   └── .gitkeep
│
├── tests/
│   └── .gitkeep
│
├── logs/
│   └── .gitkeep
│
├── .gitignore
├── requirements.txt
├── .env.example
└── README.md
```

Additional modules will be introduced in later phases as the pipeline develops.

## 8. Development Roadmap

### Phase 1: Project Setup and Dataset Preparation

- Create the project directory structure.
- Prepare the sales CSV dataset.
- Configure the Python environment.
- Create the initial dependency and configuration files.
- Validate the dataset.

**Status:** Planned

### Phase 2: Data Extraction

- Read CSV records using Python and Pandas.
- Validate source columns and data types.
- Handle file-reading errors.
- Record extraction statistics.

**Status:** Planned

### Phase 3: Data Loading

- Create an SQLite database.
- Define the raw sales table.
- Load extracted records into SQLite.
- Verify database records.

**Status:** Planned

### Phase 4: Data Transformation

- Identify and handle duplicate records.
- Handle missing and invalid values.
- Calculate revenue.
- Create SQL queries for analytical metrics.
- Prepare clean analytical tables or views.

**Status:** Planned

### Phase 5: Dashboard Development

- Build a Streamlit dashboard.
- Display sales KPIs.
- Create monthly revenue charts.
- Display product and city-wise analytics.
- Add useful data filters.

**Status:** Planned

### Phase 6: Integration, Testing and Deployment Preparation

- Connect the complete ELT workflow.
- Run the pipeline end to end.
- Test repeated executions and data correctness.
- Verify dashboard results.
- Prepare GitHub documentation and deployment instructions.

**Status:** Planned

## 9. Local Setup

### Prerequisites

- Python 3.11 or newer
- Git (optional during initial development)
- VS Code or Antigravity

### Windows PowerShell

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify Python and Pandas:

```powershell
python --version
python -c "import pandas; print(pandas.__version__)"
```

These are initial setup instructions. The complete pipeline will become runnable as its modules are implemented in subsequent phases.

## 10. Testing Strategy

The project will be validated incrementally.

- Dataset schema and record-count validation
- Missing-value and duplicate checks
- Database loading verification
- SQL transformation correctness
- Pipeline integration testing
- Dashboard data consistency checks

Tests will be added as the relevant functionality is implemented.

## 11. Future Deployment

The project will initially run locally. After the six development phases are completed, suitable deployment options for the dashboard and database will be evaluated.

No cloud deployment or hosted database is assumed to be available at the beginning.

## 12. Expected Outcome

The final goal is a functional, beginner-friendly ELT data engineering project that demonstrates:

- Source data ingestion
- Raw data storage
- SQL-based transformations
- Business analytics
- Data visualization
- Modular Python development
- Basic testing and reproducibility

The project is intended as a practical learning project and portfolio demonstration of fundamental ELT concepts.

---

**Project:** Sales Data ELT Pipeline  
**Category:** Data Engineering  
**Architecture:** Extract → Load → Transform → Analyze  
**Development plan:** Six phases  
**Initial execution:** Local environment  
**Database:** SQLite
