from database import supabase

print("Connecting to Supabase...")

response = supabase.table("tracked_products").select("*").execute()

print("Connection successful!")
print(response.data)