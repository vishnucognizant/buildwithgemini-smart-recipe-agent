import os
from google.cloud import firestore

# Hardcode project ID as string per instructions
PROJECT_ID = "qwiklabs-gcp-02-f082f30c93f8"

db = firestore.Client(project=PROJECT_ID)

seed_recipes = [
    {
        "id": "avocado-toast",
        "name": "Avocado Toast with Poached Egg",
        "cuisine": "American",
        "prep_time_mins": 10,
        "calories": 320,
        "ingredients": [
            "2 slices sourdough bread",
            "1 ripe avocado",
            "2 poached eggs",
            "1 tbsp olive oil",
            "Salt, pepper, and chili flakes"
        ],
        "instructions": "Toast the sourdough slices. Mash avocado with olive oil, salt, and pepper. Spread mashed avocado evenly over toast and top each slice with a poached egg and chili flakes.",
        "tags": ["breakfast", "quick", "vegetarian"]
    },
    {
        "id": "mediterranean-quinoa-bowl",
        "name": "Mediterranean Quinoa Bowl",
        "cuisine": "Mediterranean",
        "prep_time_mins": 20,
        "calories": 450,
        "ingredients": [
            "1 cup cooked quinoa",
            "1/2 cup cherry tomatoes, halved",
            "1/2 cup cucumber, diced",
            "1/4 cup feta cheese, crumbled",
            "1/4 cup kalamata olives",
            "2 tbsp lemon tahini dressing"
        ],
        "instructions": "Place cooked quinoa in a bowl. Arrange cherry tomatoes, cucumber, feta cheese, and olives over quinoa. Drizzle with lemon tahini dressing before serving.",
        "tags": ["lunch", "healthy", "vegetarian", "gluten-free"]
    },
    {
        "id": "garlic-butter-salmon",
        "name": "Garlic Butter Salmon with Asparagus",
        "cuisine": "Seafood",
        "prep_time_mins": 25,
        "calories": 520,
        "ingredients": [
            "2 salmon fillets",
            "1 bunch fresh asparagus",
            "3 tbsp butter",
            "3 cloves garlic, minced",
            "1 tbsp lemon juice",
            "Salt and black pepper"
        ],
        "instructions": "Season salmon and asparagus with salt and pepper. Melt butter in a skillet over medium-high heat, add minced garlic, then sear salmon fillets 4 minutes per side. Toss asparagus in garlic butter until tender-crisp.",
        "tags": ["dinner", "keto", "high-protein", "gluten-free"]
    },
    {
        "id": "classic-carbonara",
        "name": "Classic Creamy Carbonara",
        "cuisine": "Italian",
        "prep_time_mins": 20,
        "calories": 650,
        "ingredients": [
            "200g spaghetti",
            "100g guanciale or pancetta, diced",
            "2 large egg yolks + 1 whole egg",
            "50g Pecorino Romano cheese, freshly grated",
            "Freshly cracked black pepper"
        ],
        "instructions": "Boil spaghetti until al dente. Crisp guanciale in a pan. Whisk egg yolks, whole egg, and Pecorino Romano together. Toss pasta with guanciale, remove from heat, quickly stir in egg mixture with pasta water until creamy.",
        "tags": ["dinner", "pasta", "classic"]
    }
]

def seed():
    print(f"Seeding Firestore collection 'recipes' in project '{PROJECT_ID}'...")
    recipes_ref = db.collection("recipes")
    for recipe in seed_recipes:
        doc_id = recipe["id"]
        data = {k: v for k, v in recipe.items() if k != "id"}
        recipes_ref.document(doc_id).set(data)
        print(f"  ✓ Added recipe: {recipe['name']} (ID: {doc_id})")
    print("Seeding complete!")

if __name__ == "__main__":
    seed()
