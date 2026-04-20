from sqlalchemy import create_engine, text

# Your connection string
DB_URL = "postgresql://leadgen:W69ogxJ0NED5A6xxC2j7Ru3rjLh0BdG8@dpg-d7isf4n7f7vs739dn270-a.oregon-postgres.render.com/leadgen_krch"

# CHANGE THIS to the username you signed up with
USERNAME_TO_PROMOTE = "sachin" 

engine = create_engine(DB_URL)

with engine.begin() as conn:
    print(f"Promoting user: {USERNAME_TO_PROMOTE}...")
    result = conn.execute(
        text("UPDATE users SET role = 'admin', is_approved = 1, credits = 99999 WHERE username = :name"),
        {"name": USERNAME_TO_PROMOTE}
    )
    print("✅ Success! You are now an Admin with 99,999 credits.")
