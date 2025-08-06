from flask import Flask, jsonify, render_template, request
from database.earthquake_database import EarthquakeDatabase
from main import DailyUpdateScraper
import os
import threading
from datetime import datetime

app = Flask(__name__)
eq_db = EarthquakeDatabase()

# Global variable to track scraper status
scraper_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "current_progress": None,
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health_check():
    """Health check endpoint for Docker container monitoring"""
    try:
        # Test database connection
        from sqlalchemy import text

        # Use Try-Finally for session close
        try:
            session = eq_db.get_session()
            session.execute(text("SELECT 1"))
        finally:
            session.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return jsonify(
        {
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/date-range")
def get_available_date_range():
    """Get the available date range and gaps in earthquake data"""
    try:
        from sqlalchemy import text

        try:
            session = eq_db.get_session()

            # Get min and max dates
            date_range = session.execute(
                text("""
                SELECT 
                    MIN(DATE(datetime)) as min_date,
                    MAX(DATE(datetime)) as max_date
                FROM seismic_event 
                WHERE datetime IS NOT NULL
            """)
            ).fetchone()

            # Get dates with earthquake data (for enabling/disabling specific dates)
            available_dates = session.execute(
                text("""
                SELECT DISTINCT DATE(datetime) as available_date
                FROM seismic_event 
                WHERE datetime IS NOT NULL
                ORDER BY available_date
            """)
            ).fetchall()
        finally:
            session.close()

        # Convert to lists for JSON response
        available_date_list = [str(date[0]) for date in available_dates]

        return jsonify(
            {
                "min_date": str(date_range[0]) if date_range[0] else "2018-01-01",
                "max_date": str(date_range[1]) if date_range[1] else "2025-12-31",
                "available_dates": available_date_list,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/earthquakes")
def get_earthquakes():
    # Extract query parameters from the request
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    magnitude_min = request.args.get("magnitude_min", type=float)
    magnitude_max = request.args.get("magnitude_max", type=float)
    location = request.args.get("location")
    origin = request.args.get("origin")
    lat_min = request.args.get("lat_min", type=float)
    lat_max = request.args.get("lat_max", type=float)
    lon_min = request.args.get("lon_min", type=float)
    lon_max = request.args.get("lon_max", type=float)

    # Use your filtered database method with parameters
    result = eq_db.get_earthquakes_filtered(
        date_from=date_from,
        date_to=date_to,
        magnitude_min=magnitude_min,
        magnitude_max=magnitude_max,
        location=location,
        origin=origin,
        lat_min=lat_min,
        lat_max=lat_max,
        lon_min=lon_min,
        lon_max=lon_max,
    )

    # Handle both old format (list) and new format (dict) for backward compatibility
    if isinstance(result, list):
        # Old format - just earthquake list
        return jsonify({"total": len(result), "earthquakes": result})
    else:
        # New format - dict with metadata including override info
        return jsonify(result)


def check_admin_token():
    """Check if valid admin token is provided"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise ValueError("ADMIN TOKEN environment variable required")

    provided_token = request.args.get("token")
    return provided_token == admin_token


@app.route("/admin")
def admin_panel():
    """Admin panel dashboard with system status and manual controls"""
    if not check_admin_token():
        return "Access Denied. Valid admin token required.", 403

    # Get database statistics
    try:
        # Simple stats query
        from sqlalchemy import text

        try:
            session = eq_db.get_session()

            # Count total earthquakes
            total_count = session.execute(
                text("SELECT COUNT(*) FROM seismic_event")
            ).scalar()

            # Count this month
            current_month_count = session.execute(
                text("""
                SELECT COUNT(*) FROM seismic_event 
                WHERE EXTRACT(year FROM datetime) = EXTRACT(year FROM NOW())
                AND EXTRACT(month FROM datetime) = EXTRACT(month FROM NOW())
            """)
            ).scalar()

            # Latest earthquake with proper NULL handling
            latest_eq = session.execute(
                text("""
                SELECT 
                    eq_no,
                    datetime,
                    COALESCE(region, 'Unknown Region') as region,
                    COALESCE(magnitude_str, 'Unknown') as magnitude_str
                FROM seismic_event 
                WHERE datetime IS NOT NULL
                ORDER BY datetime DESC 
                LIMIT 1
            """)
            ).fetchone()
        finally:
            session.close()

        db_stats = {
            "total_earthquakes": total_count or 0,
            "current_month": current_month_count or 0,
            "latest_earthquake": {
                "eq_no": str(latest_eq[0])
                if latest_eq and latest_eq[0] is not None
                else "No Data",
                "datetime": latest_eq[1].strftime("%Y-%m-%d %H:%M:%S")
                if latest_eq and latest_eq[1]
                else "No Data",
                "region": latest_eq[2] if latest_eq and latest_eq[2] else "No Data",
                "magnitude": latest_eq[3] if latest_eq and latest_eq[3] else "No Data",
            },
        }

    except Exception as e:
        db_stats = {"error": str(e)}

    return render_template(
        "admin.html",
        scraper_status=scraper_status,
        db_stats=db_stats,
        admin_token=request.args.get("token"),
    )


@app.route("/admin/trigger")
def admin_trigger():
    """Manual trigger for daily scraper"""
    if not check_admin_token():
        return "Access Denied. Valid admin token required.", 403

    if scraper_status["running"]:
        return jsonify({"error": "Scraper is already running"}), 400

    # Start scraper in background thread
    def run_scraper():
        global scraper_status
        scraper_status["running"] = True
        scraper_status["last_run"] = datetime.now()
        scraper_status["current_progress"] = "Starting scraper..."

        try:
            scraper = DailyUpdateScraper()
            result = scraper.process_daily_updates()
            scraper_status["last_result"] = result
            scraper_status["current_progress"] = "Completed successfully"
        except Exception as e:
            scraper_status["last_result"] = {"error": str(e)}
            scraper_status["current_progress"] = f"Failed: {str(e)}"
        finally:
            scraper_status["running"] = False

    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()

    return jsonify({"message": "Scraper started successfully", "status": "running"})


@app.route("/admin/status")
def admin_status():
    """Get current scraper status (for AJAX polling)"""
    if not check_admin_token():
        return "Access Denied. Valid admin token required.", 403

    return jsonify(scraper_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
