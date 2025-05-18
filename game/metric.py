"""

## 1 Pre-processing  —  normalise the four ingredients once

For each game *g* and faction *f*:

| symbol                                        | definition                          | "good" direction |
| --------------------------------------------- | ----------------------------------- | ---------------- |
| $W_{g,f}$                                     | **Win factor** 1 / 0.5 / 0          | ↑                |
| $C_{g,f}=1-\tfrac{\text{dead}}{\text{total}}$ | **Casualty efficiency**             | ↑                |
| $Q_{g,f}=S/5$                                 | **Strategy quality**                | ↑                |
| $T_g$                                         | raw duration (s) for the whole game | ↓                |

Time gets the usual log compression to damp out outliers:

$$
D_{g} \;=\; 1 - \frac{\log (1+T_{g}) - \log(1+T_{\min})}
                         {\log (1+T_{\max}) - \log(1+T_{\min})}
$$

$D_g\in[0,1]$ with **higher = faster win**.
$T_{\min},T_{\max}$ are taken over the *entire* 50-game batch once.

---

## 2 Game-level efficiency bundle (no win/loss yet)

$$
E_{g,f} \;=\; \tfrac13\bigl(C_{g,f}+Q_{g,f}+D_{g}\bigr)
\qquad\in[0,1]
$$

It is a simple mean: users reading your paper can still inspect each term, but you only carry one number forward.

---

## 3 Aggregate to the **Model Efficiency Score (MES)**

For a model *m* that appears in a set $G_m$ of games:

$$
\text{MES}_m \;=\; \frac{1}{|G_m|}\sum_{g\in G_m}E_{g,f(m,g)}
$$

$f(m,g)$ is the faction controlled by model *m* in game *g* (1 or 2).
MES alone says "this model tends to fight clean, fast and with better planning", ignoring wins.

---

## 4 Aggregate to the **Empirical Win Rate (EWR)**

$$
\text{EWR}_m \;=\; \frac{1}{|G_m|}\sum_{g\in G_m} W_{g,f(m,g)}
$$

Exactly the proportion of victories (0 – 1, ties count 0.5).

---

## 5 Bring them together: the ** Overall Benchmark Score (OBS)**

$$
\boxed{\;
\text{OBS}_m = 100 \bigl( 0.6 \,\text{EWR}_m + 0.4 \,\text{MES}_m \bigr)
\;}
$$

* **Why 0.6 / 0.4?**

  * Reviewers first care who wins (primary objective) → 60 %.
  * The *way* you win still matters → 40 %.
    If you later collect human preference data you can re-fit the weights, but fixed constants keep the benchmark deterministic today.

* **Scale:** 0 – 100 fits nicely into result tables and bar plots.

---

## 6 Description

> **Overall metric.**
> For each model we report the ** Overall Benchmark Score (OBS)**,
>
> $$
> \text{OBS}=100\bigl(0.6\,\text{EWR}+0.4\,\text{MES}\bigr),
> $$
>
> where the Empirical Win-Rate (EWR) is the fraction of victories over 50 mirrored seeds, and the Model Efficiency Score (MES) averages casualty efficiency, time efficiency, and a 0–5 expert tactical-reasoning rubric after min–max normalisation.
> This single headline number preserves interpretability (all sub-metrics are still logged) while rewarding both *winning* and *how* the win is achieved.
>
> We distinguish between complete victories (all enemy units destroyed) and half-annihilation victories (more surviving units when time limit is reached). Complete victories are worth 1.0 in the EWR calculation, while half-annihilation victories are worth 0.5, equivalent to a tie. This ensures models are rewarded for decisive victories while still recognizing dominance in time-constrained scenarios.

"""

import glob, json, math, pandas as pd
import os

def normalise_time(t, t_min, t_max):
    return 1 - (math.log1p(t)-math.log1p(t_min)) / (math.log1p(t_max)-math.log1p(t_min))

# Path to experiment reports
files = glob.glob("experiment_reports/*.json")
raw = []

for f in files:
    # Skip any non-experiment files that might be in the directory
    if not os.path.basename(f).startswith("experiment_"):
        continue
    try:
        with open(f, 'r') as file:
            data = json.load(file)
            raw.append(data)
    except json.JSONDecodeError:
        print(f"Error: Could not parse {f} as JSON")
    except Exception as e:
        print(f"Error loading {f}: {str(e)}")

if not raw:
    print("No valid experiment files found!")
    exit(1)

print(f"Loaded {len(raw)} experiment files")

# Extract min/max time across all experiments
valid_files = [r for r in raw if 'result' in r and 'game_duration_seconds' in r['result']]
if not valid_files:
    print("No valid experiment data found with game duration!")
    exit(1)

t_min = min(r['result']['game_duration_seconds'] for r in valid_files)
t_max = max(r['result']['game_duration_seconds'] for r in valid_files)

print(f"Time range: {t_min:.2f}s - {t_max:.2f}s")

# Process all experiments
records = []
for r in raw:
    # Skip files with missing data
    if not all(k in r for k in ['result', 'units_info', 'strategy_scores', 'model_info']):
        print(f"Skipping incomplete experiment: {r.get('experiment_id', 'unknown')}")
        continue
    
    # Time efficiency
    D = normalise_time(r['result']['game_duration_seconds'], t_min, t_max)
    
    # Process each faction
    for fac in ('1', '2'):
        if fac not in r['units_info'] or fac not in r['strategy_scores'] or fac not in r['model_info']:
            continue
            
        # Casualty efficiency
        dead = r['units_info'][fac]['dead']
        total = r['units_info'][fac]['total']
        C = 1 - dead/total
        
        # Strategy quality
        Q = r['strategy_scores'][fac] / 10  # Normalized to [0,1]
        
        # Combined efficiency
        E = (C + Q + D) / 3
        
        # Win factor (1 for win, 0.5 for tie or half win, 0 for loss)
        if r['result']['is_tie']:
            W = 0.5
        else:
            is_half_win = r['result'].get('is_half_win', False)
            
            if r['result']['winner_faction'] == int(fac):
                # 如果是半歼胜利，给0.5分，否则给1分
                W = 0.5 if is_half_win else 1
            else:
                W = 0
        
        # Get model name
        model = r['model_info'][fac]
        
        # Save record
        records.append({
            'model': model,
            'faction': fac,
            'experiment_id': r.get('experiment_id', 'unknown'),
            'E': E,
            'W': W,
            'C': C,  # Store sub-metrics for detailed reporting
            'Q': Q,
            'D': D
        })

# Create DataFrame for analysis
df = pd.DataFrame(records)

# Report model participation
model_games = df.groupby('model').size()
print("\nModel participation counts:")
print(model_games)

# Calculate metrics for each model
stats = df.groupby('model').agg(
    EWR=('W', 'mean'),  # Empirical Win Rate
    MES=('E', 'mean'),  # Model Efficiency Score
    CasualtyEff=('C', 'mean'),
    StrategyQual=('Q', 'mean'),
    TimeEff=('D', 'mean'),
    Games=('model', 'count')
)

# Calculate OBS (Overall Benchmark Score)
stats['OBS'] = 100 * (0.6 * stats.EWR + 0.4 * stats.MES)

# Sort by OBS
sorted_stats = stats.sort_values('OBS', ascending=False)

# Print the final report
print("\n=== STARBENCH LLM PERFORMANCE REPORT ===")
print("\nOverall Ranking by OBS (Overall Benchmark Score):")
print(sorted_stats[['OBS', 'EWR', 'MES', 'Games']].round(2))

print("\nDetailed metrics:")
print(sorted_stats[['CasualtyEff', 'StrategyQual', 'TimeEff']].round(2))

print("\nScoring notes:")
print("- EWR (Empirical Win Rate): Full win = 1.0, Half-annihilation win = 0.5, Tie = 0.5, Loss = 0")
print("- Half-annihilation win: When time limit (600s) is reached, the faction with more surviving units")
print("- MES (Model Efficiency Score): Average of Casualty Efficiency, Strategy Quality, and Time Efficiency")
print("- OBS = 100 * (0.6 * EWR + 0.4 * MES)")

# Save to CSV
result_path = "experiment_reports/final_results.csv"
sorted_stats.round(2).to_csv(result_path)
print(f"\nFull results saved to {result_path}")

# Optional: Generate bar chart visualization
try:
    import matplotlib.pyplot as plt
    
    plt.figure(figsize=(12, 6))
    
    # Plot OBS scores
    sorted_stats['OBS'].plot(kind='bar', color='darkblue')
    
    plt.title('LLM Performance in StarBench (OBS Score)', fontsize=14)
    plt.ylabel('Overall Benchmark Score (0-100)', fontsize=12)
    plt.xlabel('Model', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    chart_path = "experiment_reports/performance_chart.png"
    plt.savefig(chart_path)
    print(f"Performance chart saved to {chart_path}")
    
except ImportError:
    print("Matplotlib not available - skipping chart generation")
