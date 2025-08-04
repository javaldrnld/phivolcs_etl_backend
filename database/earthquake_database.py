from dotenv import load_dotenv
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import logging
from pathlib import Path
from datetime import datetime
from database.models import Base, SeismicEvent, Intensities
import json

# Load env
load_dotenv()

REGION_PROVINCE_MAPPING = {
    "Region I (Ilocos Region)": [
        "Ilocos Norte",
        "Ilocos Sur",
        "La Union",
        "Pangasinan",
    ],
    "Region II (Cagayan Valley)": [
        "Batanes",
        "Cagayan",
        "Isabela",
        "Nueva Vizcaya",
        "Quirino",
    ],
    "Region III (Central Luzon)": [
        "Aurora",
        "Bataan",
        "Bulacan",
        "Nueva Ecija",
        "Pampanga",
        "Tarlac",
        "Zambales",
    ],
    "Region IV-A (CALABARZON)": ["Batangas", "Cavite", "Laguna", "Quezon", "Rizal"],
    "Region IV-B (MIMAROPA)": [
        "Marinduque",
        "Occidental Mindoro",
        "Oriental Mindoro",
        "Palawan",
        "Romblon",
    ],
    "Region V (Bicol)": [
        "Albay",
        "Camarines Norte",
        "Camarines Sur",
        "Catanduanes",
        "Masbate",
        "Sorsogon",
    ],
    "Region VI (Western Visayas)": [
        "Aklan",
        "Antique",
        "Capiz",
        "Guimaras",
        "Iloilo",
        "Negros Occidental",
    ],
    "Region VII (Central Visayas)": ["Bohol", "Cebu", "Negros Oriental", "Siquijor"],
    "Region VIII (Eastern Visayas)": [
        "Biliran",
        "Eastern Samar",
        "Leyte",
        "Northern Samar",
        "Samar",
        "Southern Leyte",
    ],
    "Region IX (Zamboanga Peninsula)": [
        "Zamboanga del Norte",
        "Zamboanga del Sur",
        "Zamboanga Sibugay",
    ],
    "Region X (Northern Mindanao)": [
        "Bukidnon",
        "Camiguin",
        "Lanao del Norte",
        "Misamis Occidental",
        "Misamis Oriental",
    ],
    "Region XI (Davao)": [
        "Davao de Oro",
        "Davao del Norte",
        "Davao del Sur",
        "Davao Occidental",
        "Davao Oriental",
    ],
    "Region XII (SOCCSKSARGEN)": [
        "Cotabato",
        "Sarangani",
        "South Cotabato",
        "Sultan Kudarat",
    ],
    "Region XIII (Caraga)": [
        "Agusan del Norte",
        "Agusan del Sur",
        "Dinagat Islands",
        "Surigao del Norte",
        "Surigao del Sur",
    ],
    "CAR (Cordillera)": [
        "Abra",
        "Apayao",
        "Benguet",
        "Ifugao",
        "Kalinga",
        "Mountain Province",
    ],
    "BARMM": [
        "Basilan",
        "Lanao del Sur",
        "Maguindanao del Norte",
        "Maguindanao del Sur",
        "Sulu",
        "Tawi-Tawi",
    ],
    "NCR (Metro Manila)": [
        "Manila",
        "Caloocan",
        "Las Piñas",
        "Makati",
        "Malabon",
        "Mandaluyong",
        "Marikina",
        "Muntinlupa",
        "Navotas",
        "Parañaque",
        "Pasay",
        "Pasig",
        "Pateros",
        "Quezon City",
        "San Juan",
        "Taguig",
        "Valenzuela",
    ],
}

INTENSITY_MAPPING = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}


# Helper function to map short region names to full region names
def map_region_name(short_region_name):
    """Map frontend region names to backend REGION_PROVINCE_MAPPING keys"""
    region_mapping = {
        "NCR": "NCR (Metro Manila)",
        "CAR": "CAR (Cordillera)",
        "Region I": "Region I (Ilocos Region)",
        "Region II": "Region II (Cagayan Valley)",
        "Region III": "Region III (Central Luzon)",
        "Region IV-A": "Region IV-A (CALABARZON)",
        "Region IV-B": "Region IV-B (MIMAROPA)",
        "Region V": "Region V (Bicol)",
        "Region VI": "Region VI (Western Visayas)",
        "Region VII": "Region VII (Central Visayas)",
        "Region VIII": "Region VIII (Eastern Visayas)",
        "Region IX": "Region IX (Zamboanga Peninsula)",
        "Region X": "Region X (Northern Mindanao)",
        "Region XI": "Region XI (Davao)",
        "Region XII": "Region XII (SOCCSKSARGEN)",
        "Region XIII": "Region XIII (Caraga)",
        "BARMM": "BARMM",
    }
    return region_mapping.get(short_region_name, short_region_name)


# Create a class
class EarthquakeDatabase:
    def __init__(self):
        self.logger = self._setup_logger()

        # Load all at once
        required_vars = ["DB_NAME", "DB_HOST", "DB_PORT", "DB_USERNAME", "DB_PASSWORD"]
        missing_vars = []

        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            # Setattr -> dynamically set attributes from data
            setattr(self, var.lower(), value)
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        self.db_string = f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def _setup_logger(self):
        """Configure logging for the connection"""
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logger = logging.getLogger("connection_db")
        logger.setLevel(logging.DEBUG)

        # File Handler
        if not logger.handlers:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = logs_dir / f"connection_db_{timestamp}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)

            file_format = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)

        return logger

    def export_to_sql_dump(self, filename="2018_2025_earthquake_data.sql"):
        """Export entire database to SQL dump file"""
        try:
            import subprocess

            # Database config already loaded in __init__!
            self.logger.info(f"Starting database export to {filename}")
            self.logger.info(
                f"Exporting database '{self.db_name}' from {self.db_host}:{self.db_port}"
            )
            self.logger.info(f"Username: {self.db_username}")

            # Step 3 - Build pg_dump command
            cmd = [
                "pg_dump",
                f"--host={self.db_host}",
                f"--port={self.db_port}",
                f"--username={self.db_username}",
                f"--dbname={self.db_name}",
                "--verbose",  # Show progress
                "--clean",  # Add DROP statements
                "--if-exists",  # Safe DROP statements
                f"--file={filename}",  # Output File
            ]

            # Step 4 - Handle password
            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password

            # Log command
            safe_cmd = [arg for arg in cmd if not arg.startswith("--password")]
            self.logger.info(f"Running command: {' '.join(safe_cmd)}")

            # Step 5 - Execute command
            self.logger.info("Starting pg_dump execution")
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=300
            )

            # Step 6: Check Results
            if result.returncode == 0:
                # Success
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    file_size_mb = file_size / (1024 * 1024)

                    self.logger.info("Database export successfull")
                    self.logger.info(f"File: {filename}")
                    self.logger.info(f"Size: {file_size_mb:.2f} MB")

                    return {
                        "success": True,
                        "filename": filename,
                        "size_mb": file_size_mb,
                        "message": f"Database exported successfully to {filename}",
                    }
                else:
                    raise Exception("Export command succeeded but file was not created")
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                self.logger.error(f"pg_dump failed: {error_msg}")
                raise Exception(f"pg_dump failed: {error_msg}")

        except subprocess.TimeoutExpired:
            self.logger.error("Database export timed out (>5 minutes)")
            raise Exception("Database export timed out")
        except FileNotFoundError:
            self.logger.error(
                "pg_dump command not found. Please install PostgreSQL client tools"
            )
            raise Exception(
                "pg_dump command not found. Please install PostgreSQL client tools"
            )
        except Exception as e:
            self.logger.error(f"Database export failed: {e}")
            raise Exception(f"Database export failed: {e}")

    # Setup fresh database
    def setup_fresh_database(self):
        """Set up clean database structure for new installations"""
        try:
            self.logger.info("Setting up fresh database structure")

            # Connect to database
            self.connect()

            # Create all tables
            self.create_tables()

            self.logger.info("Fresh database setup completed successfully")
            return {
                "success": True,
                "message": "Database structure created successfully",
            }
        except Exception as e:
            self.logger.error(f"Fresh database setup failed: {e}")
            raise Exception(f"Database setup failed: {e}")

    # Import sfrom sql dump
    def import_from_sql_dump(self, sql_file):
        """Import data from SQL dump file into database"""
        try:
            import subprocess
            import os

            # Check if SQL file exists
            if not os.path.exists(sql_file):
                raise Exception(f"SQL dump file not found: {sql_file}")

            file_size = os.path.getsize(sql_file)
            file_size_mb = file_size / (1024 * 1024)

            self.logger.info(f"Starting database import from {sql_file}")
            self.logger.info(f"File size: {file_size_mb:.2f} MB")
            self.logger.info(
                f"Target database: {self.db_name} at {self.db_host}:{self.db_port}"
            )

            # Build psql command for import
            cmd = [
                "psql",
                f"--host={self.db_host}",
                f"--port={self.db_port}",
                f"--username={self.db_username}",
                f"--dbname={self.db_name}",
                "--quiet",  # Suppress unnecessary output
                f"--file={sql_file}",
            ]

            # Handle password securely
            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password

            # Log command (without password)
            safe_cmd = [arg for arg in cmd if not arg.startswith("--password")]
            self.logger.info(f"Running command: {' '.join(safe_cmd)}")

            # Execute psql import
            self.logger.info("Starting psql import execution...")
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout (imports take longer)
            )

            # Check results
            if result.returncode == 0:
                self.logger.info("Database import completed successfully")

                # Get basic stats
                try:
                    session = self.get_session()
                    eq_count = session.execute(
                        text("SELECT COUNT(*) FROM seismic_event")
                    ).scalar()
                    intensity_count = session.execute(
                        text("SELECT COUNT(*) FROM intensities")
                    ).scalar()
                    session.close()

                    self.logger.info(
                        f"Imported {eq_count} earthquakes with {intensity_count} intensity records"
                    )

                    return {
                        "success": True,
                        "filename": sql_file,
                        "earthquake_count": eq_count,
                        "intensity_count": intensity_count,
                        "message": f"Successfully imported {eq_count} earthquakes from {sql_file}",
                    }
                except Exception as stats_error:
                    self.logger.warning(
                        f"Import succeeded but couldn't get stats: {stats_error}"
                    )
                    return {
                        "success": True,
                        "filename": sql_file,
                        "message": "Import completed successfully (stats unavailable)",
                    }
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                self.logger.error(f"psql import failed: {error_msg}")
                raise Exception(f"Database import failed: {error_msg}")

        except subprocess.TimeoutExpired:
            self.logger.error("Database import timed out (>10 minutes)")
            raise Exception("Database import timed out")
        except FileNotFoundError:
            self.logger.error(
                "psql command not found. Please install PostgreSQL client tools"
            )
            raise Exception(
                "psql command not found. Please install PostgreSQL client tools"
            )
        except Exception as e:
            self.logger.error(f"Database import failed: {e}")
            raise Exception(f"Database import failed: {e}")

    def connect(self, max_retries=3):
        # Setup engine
        if hasattr(self, "engine") and self.engine is not None:
            self.logger.error("Reusing existing engine")
            return self.engine
        else:
            for attempt in range(max_retries):
                try:
                    self.engine = create_engine(self.db_string)
                    self.engine.connect()
                    self.logger.info("Connection successful")
                    return self.engine
                except Exception as e:
                    self.logger.warning(f"Connection attempt {attempt + 1}")
                    if attempt == max_retries - 1:
                        self.logger.error("All connections attempt failed")
                        raise

    def verify_import(self, expected_count=None):
        """Verify imported data integrity and return statistics"""
        try:
            from sqlalchemy import text

            self.logger.info("Verifying imported data integrity...")
            session = self.get_session()

            # Get comprehensive stats
            stats = {}

            # Basic counts
            stats["earthquake_count"] = session.execute(
                text("SELECT COUNT(*) FROM seismic_event")
            ).scalar()
            stats["intensity_count"] = session.execute(
                text("SELECT COUNT(*) FROM intensities")
            ).scalar()

            # Date range
            date_range = session.execute(
                text("""
                SELECT MIN(datetime) as min_date, MAX(datetime) as max_date 
                FROM seismic_event WHERE datetime IS NOT NULL
            """)
            ).fetchone()
            stats["date_range"] = {
                "min_date": str(date_range[0]) if date_range[0] else None,
                "max_date": str(date_range[1]) if date_range[1] else None,
            }

            # Data quality checks
            stats["earthquakes_with_coordinates"] = session.execute(
                text("""
                SELECT COUNT(*) FROM seismic_event 
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """)
            ).scalar()

            stats["earthquakes_with_intensities"] = session.execute(
                text("""
                SELECT COUNT(DISTINCT eq_id) FROM intensities
            """)
            ).scalar()

            session.close()

            # Calculate percentages
            if stats["earthquake_count"] > 0:
                stats["coordinate_percentage"] = (
                    stats["earthquakes_with_coordinates"] / stats["earthquake_count"]
                ) * 100
                stats["intensity_percentage"] = (
                    stats["earthquakes_with_intensities"] / stats["earthquake_count"]
                ) * 100

            # Validation
            validation_passed = True
            issues = []

            if expected_count and stats["earthquake_count"] != expected_count:
                issues.append(
                    f"Expected {expected_count} earthquakes, got {stats['earthquake_count']}"
                )
                validation_passed = False

            if stats["coordinate_percentage"] < 95:
                issues.append(
                    f"Only {stats['coordinate_percentage']:.1f}% of earthquakes have coordinates"
                )

            stats["validation_passed"] = validation_passed
            stats["issues"] = issues

            # Log results
            self.logger.info("Import Verification Results:")
            self.logger.info(f"   Earthquakes: {stats['earthquake_count']:,}")
            self.logger.info(f"   Intensities: {stats['intensity_count']:,}")
            self.logger.info(
                f"   Date Range: {stats['date_range']['min_date']} to {stats['date_range']['max_date']}"
            )
            self.logger.info(f"   Coordinates: {stats['coordinate_percentage']:.1f}%")
            self.logger.info(
                f"   With Intensities: {stats['intensity_percentage']:.1f}%"
            )

            if validation_passed:
                self.logger.info("Data validation passed")
            else:
                self.logger.warning(f"Validation issues: {'; '.join(issues)}")

            return stats

        except Exception as e:
            self.logger.error(f"Import verification failed: {e}")
            raise Exception(f"Import verification failed: {e}")

    # Create table
    def create_tables(self):
        # Ensure we have engine
        # hasattr check if the object is has a specific attribute
        if not hasattr(self, "engine") or self.engine is None:
            self.connect()

        # Create tables
        try:
            Base.metadata.create_all(bind=self.engine)
            self.logger.info("Tables created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create tables: {e}")
            raise

    def get_session(self):
        # Ensure we have engine
        if not hasattr(self, "engine") or self.engine is None:
            self.connect()

        # Create session
        try:
            Session = sessionmaker(bind=self.engine)
            self.logger.info("Session created successfully")
            return Session()
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            raise

    # Function for generating keys
    def generate_business_key(self, earthquake_data):
        """Generate business key from earthquake data"""
        try:
            # Extract timestamp from filename
            filename = earthquake_data["filename"]
            match = re.match(r"^(\d{4}_\d{4}_\d{4})", filename)
            if match:
                prefix = match.group(1)
            else:
                # Fall back
                prefix = re.sub(r"_B.*$", "", filename)

            # Clean province name
            province = earthquake_data["province"].replace(" ", "_")
            province = re.sub(r"[^a-zA-Z0-9_]", "", province)

            # Generate business key
            business_key = f"{prefix}_{province}"
            self.logger.debug(f"Generated business key: {business_key}")
            return business_key

        except Exception as e:
            self.logger.error(f"Error generating business key: {e}")
            return None

    # Keep higher eq_no
    def is_better_version(self, new_eq, current_eq):
        """Higher eq_no is more accuracte"""
        new_eq_no = new_eq.get("eq_no")
        current_eq_no = current_eq.get("eq_no")

        if new_eq_no is None and current_eq_no is None:
            return False
        if new_eq_no is None:
            return False
        if current_eq_no is None:
            return True

        return new_eq_no > current_eq_no

    # Build JSON bulk
    def bulk_load_from_json(self, json_file_path):
        """Load earthquake data from JSON file into database"""
        try:
            # Load JSON file
            self.logger.info(f"Loading JSON file: {json_file_path}")
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.logger.info(f"Loaded {len(data)} earthquake records")
            self.logger.info("Deduplicating earthquakes")
            earthquake_groups = {}
            duplicates_removed = 0

            for earthquake in data:
                business_key = self.generate_business_key(earthquake)
                if not business_key:
                    continue

                if business_key not in earthquake_groups:
                    earthquake_groups[business_key] = earthquake
                else:
                    current = earthquake_groups[business_key]
                    if self.is_better_version(earthquake, current):
                        earthquake_groups[business_key] = earthquake
                        duplicates_removed += 1
                        self.logger.debug(
                            f"Updated earthquake: kept eq_no {earthquake['eq_no']} over {current['eq_no']}"
                        )
                    else:
                        duplicates_removed += 1

            data = list(earthquake_groups.values())
            self.logger.info(
                f"After deduplication: {len(data)} unique earthquakes, {duplicates_removed} duplicates removed"
            )

            # Pocess each earthquake + generate business keys
            processed_data = []
            failed_business_keys = 0

            for earthquake in data:
                business_key = self.generate_business_key(earthquake)
                if business_key:
                    earthquake["eq_business_key"] = business_key
                    earthquake["created_at"] = datetime.now()
                    earthquake["updated_at"] = datetime.now()
                    processed_data.append(earthquake)
                else:
                    failed_business_keys += 1
                    self.logger.warning(
                        f"Failed to generate business key for EQ #{earthquake.get('eq_no', 'unknown')}"
                    )

            self.logger.info(
                f"Successfully processed {len(processed_data)} records, {failed_business_keys} failed business key generation"
            )

            # Insert one-by-one with error tackling
            succesful_inserts = 0
            failed_inserts = 0

            for earthquake in processed_data:
                session = self.get_session()

                try:
                    # Create SeismicEvent object
                    eq = SeismicEvent(
                        eq_business_key=earthquake["eq_business_key"],
                        eq_no=earthquake["eq_no"],
                        datetime=earthquake["datetime"],
                        latitude_str=earthquake["latitude_str"],
                        longitude_str=earthquake["longitude_str"],
                        latitude=earthquake["latitude"],
                        longitude=earthquake["longitude"],
                        region=earthquake["region"],
                        location=earthquake["location"],
                        municipality=earthquake["municipality"],
                        province=earthquake["province"],
                        depth_km=earthquake["depth_km"],
                        depth_str=earthquake["depth_str"],
                        origin=earthquake["origin"],
                        magnitude_type=earthquake["magnitude_type"],
                        magnitude_value=earthquake["magnitude_value"],
                        magnitude_str=earthquake["magnitude_str"],
                        filename=earthquake["filename"],
                        issued_datetime=earthquake["issued_datetime"],
                        authors=earthquake["authors"],
                        created_at=earthquake["created_at"],
                        updated_at=earthquake["updated_at"],
                    )

                    # Loop through intensity
                    for intensity_data in earthquake["reported_intensities"]:
                        # Loop through location
                        for location in intensity_data["locations"]:
                            intensity_obj = Intensities(
                                intensity_type="reported",
                                intensity_value=intensity_data["intensity"],
                                location=location,
                            )
                            # Automatic foreign key -> SQLALCHEMY
                            eq.intensities.append(intensity_obj)

                    for intensity_data in earthquake["instrumental_intensities"]:
                        # Loop through location
                        for location in intensity_data["locations"]:
                            intensity_obj = Intensities(
                                intensity_type="instrumental",
                                intensity_value=intensity_data["intensity"],
                                location=location,
                            )
                            eq.intensities.append(intensity_obj)

                    # Add the eq to database
                    session.add(eq)
                    session.commit()
                    succesful_inserts += 1
                    self.logger.info(
                        f"Successfully inserted earthquake #{earthquake.get('eq_no', 'unknown')}"
                    )

                except Exception as e:
                    # Use rollback to undo changes mande in this session since the last commit
                    session.rollback()
                    failed_inserts += 1
                    self.logger.error(f"Failed to insert earthquake: {e}")
                finally:
                    session.close()

            # Return statistics
            return {
                "total_loaded": len(data),
                "processed_successfully": len(processed_data),
                "failed_business_keys": failed_business_keys,
                "succesful_inserts": succesful_inserts,
                "failed_inserts": failed_inserts,
                "ready_for_insert": len(processed_data),
            }

        except Exception as e:
            self.logger.error(f"Error in bulk_load_from_json: {e}")
            return None

    def process_live_update(self, eq_dict):
        """Insert OR Update OR Skip"""
        session = self.get_session()
        try:
            self.logger.info("Updating Seismic Event")
            business_key = self.generate_business_key(earthquake_data=eq_dict)

            if business_key:
                eq_dict["eq_business_key"] = business_key
                eq_dict["created_at"] = datetime.now()
                eq_dict["updated_at"] = datetime.now()
            else:
                self.logger.warning(
                    f"Failed to generate business key for EQ #{eq_dict.get('eq_no', 'unknown')}"
                )

            # Filter by business key and get the first matching
            existing_record = (
                session.query(SeismicEvent)
                .filter(SeismicEvent.eq_business_key == business_key)
                .first()
            )

            if not existing_record:
                self.logger.debug("Adding new seismic event to the database")
                try:
                    eq = SeismicEvent(
                        eq_business_key=eq_dict["eq_business_key"],
                        eq_no=eq_dict["eq_no"],
                        datetime=eq_dict["datetime"],
                        latitude_str=eq_dict["latitude_str"],
                        longitude_str=eq_dict["longitude_str"],
                        latitude=eq_dict["latitude"],
                        longitude=eq_dict["longitude"],
                        region=eq_dict["region"],
                        location=eq_dict["location"],
                        municipality=eq_dict["municipality"],
                        province=eq_dict["province"],
                        depth_km=eq_dict["depth_km"],
                        depth_str=eq_dict["depth_str"],
                        origin=eq_dict["origin"],
                        magnitude_type=eq_dict["magnitude_type"],
                        magnitude_value=eq_dict["magnitude_value"],
                        magnitude_str=eq_dict["magnitude_str"],
                        filename=eq_dict["filename"],
                        issued_datetime=eq_dict["issued_datetime"],
                        authors=eq_dict["authors"],
                        created_at=eq_dict["created_at"],
                        updated_at=eq_dict["updated_at"],
                    )

                    for intensity_data in eq_dict["reported_intensities"]:
                        # Loop through location
                        for location in intensity_data["locations"]:
                            intensity_obj = Intensities(
                                intensity_type="reported",
                                intensity_value=intensity_data["intensity"],
                                location=location,
                            )
                            # Automatic foreign key -> SQLALCHEMY
                            eq.intensities.append(intensity_obj)

                    for intensity_data in eq_dict["instrumental_intensities"]:
                        # Loop through location
                        for location in intensity_data["locations"]:
                            intensity_obj = Intensities(
                                intensity_type="instrumental",
                                intensity_value=intensity_data["intensity"],
                                location=location,
                            )
                            eq.intensities.append(intensity_obj)

                    # Add the eq to database
                    session.add(eq)
                    session.commit()
                    self.logger.info(
                        f"Successfully inserted earthquake #{eq_dict.get('eq_no', 'unknown')}"
                    )
                    return "Successful inserting new earthquake"

                except Exception as e:
                    # Use rollback to undo changes mande in this session since the last commit
                    session.rollback()
                    self.logger.error(f"Failed to insert earthquake: {e}")

            # Can directly access because we select all field earlier
            if existing_record.eq_no < eq_dict["eq_no"]:
                try:
                    # If latest_eq_no is greater than meaning update
                    session.query(SeismicEvent).filter(
                        SeismicEvent.eq_business_key == business_key
                    ).update(
                        {
                            SeismicEvent.eq_business_key: eq_dict["eq_business_key"],
                            SeismicEvent.eq_no: eq_dict["eq_no"],
                            SeismicEvent.datetime: eq_dict["datetime"],
                            SeismicEvent.latitude_str: eq_dict["latitude_str"],
                            SeismicEvent.longitude_str: eq_dict["longitude_str"],
                            SeismicEvent.latitude: eq_dict["latitude"],
                            SeismicEvent.longitude: eq_dict["longitude"],
                            SeismicEvent.region: eq_dict["region"],
                            SeismicEvent.location: eq_dict["location"],
                            SeismicEvent.municipality: eq_dict["municipality"],
                            SeismicEvent.province: eq_dict["province"],
                            SeismicEvent.depth_km: eq_dict["depth_km"],
                            SeismicEvent.depth_str: eq_dict["depth_str"],
                            SeismicEvent.origin: eq_dict["origin"],
                            SeismicEvent.magnitude_type: eq_dict["magnitude_type"],
                            SeismicEvent.magnitude_value: eq_dict["magnitude_value"],
                            SeismicEvent.magnitude_str: eq_dict["magnitude_str"],
                            SeismicEvent.filename: eq_dict["filename"],
                            SeismicEvent.issued_datetime: eq_dict["issued_datetime"],
                            SeismicEvent.authors: eq_dict["authors"],
                            SeismicEvent.updated_at: eq_dict["updated_at"],
                        }
                    )

                    # Clear existing intensities -> To update
                    existing_record.intensities.clear()

                    for intensity_data in eq_dict["reported_intensities"]:
                        for location in intensity_data["locations"]:
                            intensity_obj = Intensities(
                                intensity_type="reported",
                                intensity_value=intensity_data["intensity"],
                                location=location,
                            )
                            existing_record.intensities.append(intensity_obj)

                    for intensity_data in eq_dict["instrumental_intensities"]:
                        for location in intensity_data["locations"]:
                            intensity_obj = Intensities(
                                intensity_type="instrumental",
                                intensity_value=intensity_data["intensity"],
                                location=location,
                            )
                            existing_record.intensities.append(intensity_obj)

                    # Add the eq to database
                    session.commit()
                    self.logger.info(
                        f"Successfully update earthquake #{eq_dict.get('eq_no', 'unknown')}"
                    )
                    return "Successful updating earthquake"
                except Exception as e:
                    # Use rollback to undo changes mande in this session since the last commit
                    session.rollback()
                    self.logger.error(f"Failed to insert earthquake: {e}")

            else:
                self.logger.info(
                    f"Skipping earthquake - no update needed (existing eq_no: {existing_record.eq_no}, new eq_no: {eq_dict['eq_no']})"
                )
                return "Successful skipping earthquake"

        except Exception as e:
            self.logger.error(f"Error in process_live_update: {e}")
            return None
        finally:
            session.close()

    def get_earthquakes_filtered(
        self,
        date_from=None,
        date_to=None,
        magnitude_min=None,
        magnitude_max=None,
        location=None,  # Region name
        origin=None,
        lat_min=None,
        lat_max=None,
        lon_min=None,
        lon_max=None,
    ):
        try:
            from datetime import datetime
            from sqlalchemy import and_, extract

            session = self.get_session()

            # Get current year and month
            now = datetime.now()
            current_year = now.year
            current_month = now.month

            # Base query
            query = session.query(SeismicEvent)

            # Default behaviour -> IF user didnt provide the date
            if not date_from and not date_to:
                query = query.filter(
                    and_(
                        extract("year", SeismicEvent.datetime) == current_year,
                        extract("month", SeismicEvent.datetime) == current_month,
                    )
                )
            else:
                # Apply user's date filters with proper end-of-day handling
                if date_from:
                    # Convert string to datetime for comparison
                    start_datetime = datetime.strptime(date_from, "%Y-%m-%d")
                    query = query.filter(SeismicEvent.datetime >= start_datetime)

                if date_to:
                    # For end date, include the entire day by going to 23:59:59
                    end_datetime = datetime.strptime(date_to, "%Y-%m-%d")
                    end_of_day = end_datetime.replace(hour=23, minute=59, second=59)
                    query = query.filter(SeismicEvent.datetime <= end_of_day)

            override_applied = False
            if magnitude_min and magnitude_min <= 2.0:
                if date_from and date_to:
                    start_date = datetime.strptime(date_from, "%Y-%m-%d")
                    end_date = datetime.strptime(date_to, "%Y-%m-%d")
                    date_range_days = (end_date - start_date).days

                    # If over 6 months - force current month to protect performance
                    if date_range_days > 180:
                        # Clear the existing date filters and force current month
                        query = session.query(SeismicEvent).filter(
                            and_(
                                extract("year", SeismicEvent.datetime) == current_year,
                                extract("month", SeismicEvent.datetime)
                                == current_month,
                            )
                        )

                        # Apply all other filters to the override query
                        if magnitude_max:
                            query = query.filter(
                                SeismicEvent.magnitude_value <= magnitude_max
                            )
                        if location:
                            # Map short region name to full region name
                            full_region_name = map_region_name(location)
                            provinces = REGION_PROVINCE_MAPPING.get(
                                full_region_name, []
                            )
                            if provinces:
                                query = query.filter(
                                    SeismicEvent.province.in_(provinces)
                                )
                        if origin:
                            query = query.filter(
                                SeismicEvent.origin.ilike(f"%{origin}%")
                            )
                        if lat_min and lat_max and lon_min and lon_max:
                            query = query.filter(
                                and_(
                                    SeismicEvent.latitude >= lat_min,
                                    SeismicEvent.latitude <= lat_max,
                                    SeismicEvent.longitude >= lon_min,
                                    SeismicEvent.longitude <= lon_max,
                                )
                            )

                        override_applied = True
                        # Reset date variables for logging
                        date_from = f"{current_year}-{current_month:02d}-01"
                        date_to = f"{current_year}-{current_month:02d}-31"

            if not override_applied:
                # Apply normal filtering when no override
                if magnitude_min:
                    query = query.filter(SeismicEvent.magnitude_value >= magnitude_min)
                if magnitude_max:
                    query = query.filter(SeismicEvent.magnitude_value <= magnitude_max)
                if location:
                    # Map short region name to full region name
                    full_region_name = map_region_name(location)
                    provinces = REGION_PROVINCE_MAPPING.get(full_region_name, [])
                    if provinces:
                        query = query.filter(SeismicEvent.province.in_(provinces))
                if origin:
                    query = query.filter(SeismicEvent.origin.ilike(f"%{origin}%"))
                if lat_min and lat_max and lon_min and lon_max:
                    query = query.filter(
                        and_(
                            SeismicEvent.latitude >= lat_min,
                            SeismicEvent.latitude <= lat_max,
                            SeismicEvent.longitude >= lon_min,
                            SeismicEvent.longitude <= lon_max,
                        )
                    )
            earthquakes = (
                query.order_by(SeismicEvent.datetime.desc()).limit(5_000).all()
            )

            # Convert to dictionaries for JSON
            earthquake_list = []
            for eq in earthquakes:
                intensities = (
                    session.query(Intensities)
                    .filter(Intensities.eq_id == eq.eq_id)
                    .all()
                )

                # Separate by type
                reported = [i for i in intensities if i.intensity_type == "reported"]
                instrumental = [
                    i for i in intensities if i.intensity_type == "instrumental"
                ]
                earthquake_dict = {
                    "eq_no": eq.eq_no,
                    "datetime": eq.datetime.isoformat() if eq.datetime else None,
                    "region": eq.region,
                    "latitude": eq.latitude,
                    "longitude": eq.longitude,
                    "latitude_str": eq.latitude_str,
                    "longitude_str": eq.longitude_str,
                    "depth_str": eq.depth_str,
                    "origin": eq.origin,
                    "magnitude_str": eq.magnitude_str,
                }
                if reported:
                    # Find the maximum intensity value
                    max_intensity_value = max(
                        INTENSITY_MAPPING.get(i.intensity_value, 0) for i in reported
                    )
                    # Get all intensities with the maximum value
                    max_intensities = [
                        i
                        for i in reported
                        if INTENSITY_MAPPING.get(i.intensity_value, 0)
                        == max_intensity_value
                    ]
                    # Get the intensity value and all locations
                    earthquake_dict["max_reported_intensity"] = max_intensities[
                        0
                    ].intensity_value
                    locations = [i.location for i in max_intensities if i.location]
                    earthquake_dict["max_reported_location"] = "; ".join(locations)

                if instrumental:
                    # Find the maximum intensity value
                    max_intensity_value = max(
                        INTENSITY_MAPPING.get(i.intensity_value, 0)
                        for i in instrumental
                    )
                    # Get all intensities with the maximum value
                    max_intensities = [
                        i
                        for i in instrumental
                        if INTENSITY_MAPPING.get(i.intensity_value, 0)
                        == max_intensity_value
                    ]
                    # Get the intensity value and all locations
                    earthquake_dict["max_instrumental_intensity"] = max_intensities[
                        0
                    ].intensity_value
                    locations = [i.location for i in max_intensities if i.location]
                    earthquake_dict["max_instrumental_location"] = "; ".join(locations)
                earthquake_list.append(earthquake_dict)

            session.close()

            # Dynamic logging based on applied filters
            filter_info = []

            if not date_from and not date_to:
                filter_info.append("current month (default)")
            else:
                if date_from and date_to:
                    filter_info.append(f"date range {date_from} to {date_to}")
                elif date_from:
                    filter_info.append(f"from {date_from}")
                elif date_to:
                    filter_info.append(f"until {date_to}")

            if override_applied:
                filter_info.append("performance override applied")
            elif magnitude_min or magnitude_max:
                mag_range = []
                if magnitude_min:
                    mag_range.append(f"≥{magnitude_min}")
                if magnitude_max:
                    mag_range.append(f"≤{magnitude_max}")
                filter_info.append(f"magnitude {' and '.join(mag_range)}")

            if location:
                filter_info.append(f"region '{location}'")

            if origin:
                filter_info.append(f"origin contains '{origin}'")

            if lat_min and lat_max and lon_min and lon_max:
                filter_info.append(
                    f"geographic bounds ({lat_min},{lon_min}) to ({lat_max},{lon_max})"
                )

            filter_description = ", ".join(filter_info) if filter_info else "no filters"

            self.logger.info(
                f"Retrieved {len(earthquake_list)} earthquakes with filters: {filter_description}"
            )

            # Return both data and metadata
            return {
                "earthquakes": earthquake_list,
                "total_count": len(earthquake_list),
                "override_applied": override_applied,
                "override_reason": "Performance protection: magnitude ≤2.0 + date range >6 months → limited to current month"
                if override_applied
                else None,
                "filter_description": filter_description,
                "current_date_range": f"{current_year}-{current_month:02d}-01 to {current_year}-{current_month:02d}-31"
                if override_applied
                else None,
            }

        except Exception as e:
            self.logger.error(f"Error getting earthquakes: {e}")
            return []


if __name__ == "__main__":
    db = EarthquakeDatabase()
    # engine = db.connect()
    # print(f"Connection successful: {engine}")

    ## print("Test two")
    ## engine1 = db.connect()

    ## print("Second connection")
    ## engine2 = db.connect()

    ## print(f"Same engine? {engine1 is engine2}")
    # print("=== First Run (should create tables) ===")
    # start = time.time()
    # db.create_tables()
    # first_time = time.time() - start
    # print(f"First run took: {first_time:.3f} seconds")

    # print("\n=== Second Run (should skip existing tables) ===")
    # start = time.time()
    # db.create_tables()
    # second_time = time.time() - start
    # print(f"Second run took: {second_time:.3f} seconds")

    # print(f"\nSpeed difference: {first_time / second_time:.1f}x faster on second run")

    # print("Testing get_session()...")
    # session = db.get_session()
    # print(f"Session created: {session}")
    # print(f"Session engine: {session.bind}")
    # session.close()
    # print("Session closed")
    # Test bulk_load_from_json with single earthquake
    # print("=== Testing bulk_load_from_json ===")

    ## Ensure tables exist
    # print("Creating tables...")
    # db.create_tables()

    ## Test with single earthquake
    # result = db.bulk_load_from_json("earthquake_data_year_2018_2018.json")
    # print("Test Results:")
    # print(result)
    db.create_tables()
    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    for year in years:
        result = db.bulk_load_from_json(f"earthquake_data_year_{year}_{year}.json")

    print(result)
