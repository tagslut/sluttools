# Script: UI snippet for choosing matching mode (archived fragment; not a runnable module).
console.print("\n[bold cyan]Choose matching mode:[/bold cyan]")
console.print("1) Auto      – Let the tool pick the fastest reliable method (recommended)")
console.print("2) Quick     – Minimal preprocessing, good for small playlists and skipping indexing")
console.print("3) Thorough  – Build search indexes first for maximum accuracy (slower on first run)")

mode_choice = safe_prompt("Mode [1-3]", default="1")

# Map simplified choice to internal optimisation level expected downstream
if mode_choice == "1":
    opt_choice = "5" if len(entries) <= 50 else "3"
elif mode_choice == "2":
    opt_choice = "5"
else:
    opt_choice = "2"