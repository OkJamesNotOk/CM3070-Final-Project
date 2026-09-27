# NextTrack

## Setup Instructions

Before starting, open a terminal and navigate to the **project root**.

The project root should contain:

```
nexttrack/
nexttrackVue/
requirements.txt
readme.md
```

All commands below assume the terminal starts from the project root.



### 1. Set Up the Python Virtual Environment

Create a Python virtual environment:

```
py -m venv .venv
```

Activate it:

```
.\.venv\Scripts\Activate.ps1
```

Once activated, `(.venv)` should appear at the beginning of the terminal line.

Install the required Python packages:

```
pip install -r requirements.txt
```



### 2. Install the Frontend Dependencies

Make sure Node.js and npm are installed.

Navigate to the Vue project:

```
cd nexttrackVue
```

Install the required dependencies:

```
npm ci
```

This will create the `node_modules` folder and install the frontend dependencies.

Return to the project root:

```
cd ../
```



### 3. Configure the Environment File

Navigate to the Django project folder:

```
cd nexttrack\NextTrack
```

Rename:

```
.env.example
```

to:

```
.env
```

Add the required API keys and Django secret key to the `.env` file.

Return to the project root:

```
cd ../../
```



### 4. Run the Django Tests

Make sure the Python virtual environment is activated:

```
.\.venv\Scripts\Activate.ps1
```

Navigate to the Django folder:

```
cd nexttrack\NextTrack
```

Run the Django tests:

```
py manage.py test
```

### 5. Start the Django Development Server

Make sure the Python virtual environment is activated:

```
.\.venv\Scripts\Activate.ps1
```

Navigate to the folder containing `manage.py`:

```
cd nexttrack\NextTrack
```

Start the Django development server:

```
py manage.py runserver
```

Keep this terminal running while using NextTrack.



### 6. Start the Vue Development Server

Open a **new terminal** at the project root.

Navigate to the Vue project:

```
cd nexttrackVue
```

Start the development server:

```
npm run dev
```

The terminal should display a local URL similar to:

```
http://localhost:5173/
```

Open the displayed URL in a web browser.

Keep both the Django and Vue development servers running while using the application.

## API Usage

The main recommendation endpoint is:

GET /api/song/

Example:

http://127.0.0.1:8000/api/song/?artist=Mili&language=Japanese&tags=j-pop

Available search parameters:

- `artist`
- `language`
- `tags`
- `title_keywords`
- `include_similar_artists`

At least one search parameter must be provided.