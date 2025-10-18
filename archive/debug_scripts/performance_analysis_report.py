"""Generate performance analysis report with extrapolation."""

import numpy as np
import matplotlib.pyplot as plt

# Actual measured data
weeks = np.array([1, 2, 3])
lp_times = np.array([0.20, 0.32, 0.51])
mip_times = np.array([1.30, 1.96, 11.11])
variables = np.array([3956, 6588, 9220])
integer_vars = np.array([132, 216, 300])

print("="*70)
print("SOLVER PERFORMANCE ANALYSIS & EXTRAPOLATION")
print("="*70)

print("\nMeasured Performance:")
print(f"  {'Weeks':<8} {'LP Time':<12} {'MIP Time':<12} {'MIP/LP Ratio':<12}")
print(f"  {'-'*50}")
for i in range(len(weeks)):
    ratio = mip_times[i] / lp_times[i]
    print(f"  {weeks[i]:<8} {lp_times[i]:<12.2f} {mip_times[i]:<12.2f} {ratio:<12.1f}x")

# LP time is roughly linear
lp_linear = np.polyfit(weeks, lp_times, 1)
print(f"\nLP Time Model (linear):")
print(f"  time = {lp_linear[0]:.3f} * weeks + {lp_linear[1]:.3f}")

# MIP time appears exponential
# Fit exponential: time = a * exp(b * weeks)
log_mip = np.log(mip_times)
mip_exp_fit = np.polyfit(weeks, log_mip, 1)
mip_a = np.exp(mip_exp_fit[1])
mip_b = mip_exp_fit[0]

print(f"\nMIP Time Model (exponential):")
print(f"  time = {mip_a:.3f} * exp({mip_b:.3f} * weeks)")

# Calculate R-squared for MIP exponential fit
mip_pred = mip_a * np.exp(mip_b * weeks)
ss_res = np.sum((mip_times - mip_pred) ** 2)
ss_tot = np.sum((mip_times - np.mean(mip_times)) ** 2)
r2 = 1 - (ss_res / ss_tot)
print(f"  R² = {r2:.4f}")

# Extrapolate to full dataset (29 weeks)
full_weeks = 29

lp_pred_29 = np.polyval(lp_linear, full_weeks)
mip_pred_29 = mip_a * np.exp(mip_b * full_weeks)

print(f"\n{'='*70}")
print(f"EXTRAPOLATION TO 29 WEEKS (FULL DATASET)")
print(f"{'='*70}")

print(f"\nLP Relaxation (linear extrapolation):")
print(f"  Predicted time: {lp_pred_29:.1f} seconds ({lp_pred_29/60:.2f} minutes)")
print(f"  ✅ LP will solve quickly even for full dataset")

print(f"\nMIP with CBC (exponential extrapolation):")
print(f"  Predicted time: {mip_pred_29:.0f} seconds")
print(f"                  {mip_pred_29/60:.1f} minutes")
print(f"                  {mip_pred_29/3600:.2f} hours")

if mip_pred_29 > 86400:
    print(f"                  {mip_pred_29/86400:.1f} DAYS")

# Growth analysis
print(f"\n{'='*70}")
print("GROWTH ANALYSIS")
print(f"{'='*70}")

print(f"\nPer-week growth factors:")
print(f"  Week 1→2: MIP time × {mip_times[1]/mip_times[0]:.2f}")
print(f"  Week 2→3: MIP time × {mip_times[2]/mip_times[1]:.2f}")
print(f"  Average: MIP time × {np.exp(mip_b):.2f} per week")

print(f"\nProjected solve times:")
for w in [4, 6, 8, 10, 15, 20, 29]:
    t = mip_a * np.exp(mip_b * w)
    if t < 60:
        print(f"  {w:2} weeks: {t:8.1f} seconds")
    elif t < 3600:
        print(f"  {w:2} weeks: {t/60:8.1f} minutes")
    elif t < 86400:
        print(f"  {w:2} weeks: {t/3600:8.2f} hours")
    else:
        print(f"  {w:2} weeks: {t/86400:8.1f} days")

# Root cause analysis
print(f"\n{'='*70}")
print("ROOT CAUSE ANALYSIS")
print(f"{'='*70}")

print(f"\n🔍 Why is MIP so much harder than LP?")
print(f"\n1. **Weak LP Relaxation:**")
print(f"   - Integrality gap at 2 weeks: 242%")
print(f"   - This means the LP bound is very far from the integer optimum")
print(f"   - CBC must explore many branches to close this gap")

print(f"\n2. **Exponential Search Tree:**")
print(f"   - Integer variables: {integer_vars[-1]} at 3 weeks")
print(f"   - Each binary variable can double the search space")
print(f"   - 300 binary vars → theoretical 2^300 combinations")

print(f"\n3. **Symmetry:**")
print(f"   - Multiple trucks can serve the same route")
print(f"   - Many equivalent solutions exist")
print(f"   - Solver wastes time exploring symmetric branches")

# Recommendations
print(f"\n{'='*70}")
print("RECOMMENDATIONS")
print(f"{'='*70}")

print(f"\n📊 **For Current CBC Solver:**")
print(f"\n   Option 1: Relax MIP Gap Tolerance")
print(f"   - Current: 1% gap (very tight)")
print(f"   - Suggested: 5-10% gap")

# Estimate speedup from relaxed gap
gap_5_pred = mip_pred_29 * 0.1  # Rough estimate: 10x faster
gap_10_pred = mip_pred_29 * 0.05  # Rough estimate: 20x faster

print(f"   - Estimated solve time with 5% gap:  {gap_5_pred/60:.1f} min ({gap_5_pred/3600:.2f} hours)")
print(f"   - Estimated solve time with 10% gap: {gap_10_pred/60:.1f} min ({gap_10_pred/3600:.2f} hours)")

print(f"\n   Option 2: Rolling Horizon")
print(f"   - Optimize 4 weeks at a time (solves in ~30-60 seconds)")
print(f"   - Roll forward week-by-week")
print(f"   - Total time: ~7-8 optimization runs = 4-8 minutes")

print(f"\n💎 **With Commercial Solver (Gurobi/CPLEX):**")
print(f"   - 5-10x faster than CBC")
print(f"   - Better branch-and-cut algorithms")
print(f"   - Estimated full dataset: {mip_pred_29/(60*7):.1f} minutes")

print(f"\n🔧 **Model Improvements:**")
print(f"   1. Add symmetry-breaking constraints")
print(f"   2. Implement branching priorities")
print(f"   3. Add valid inequalities to strengthen LP relaxation")
print(f"   4. Pre-assign some trucks using heuristics")

# Visualization
weeks_smooth = np.linspace(1, 29, 100)
lp_smooth = np.polyval(lp_linear, weeks_smooth)
mip_smooth = mip_a * np.exp(mip_b * weeks_smooth)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Linear scale
ax1 = axes[0]
ax1.scatter(weeks, lp_times, s=100, color='green', zorder=5, label='LP (actual)', marker='o')
ax1.plot(weeks_smooth, lp_smooth, '--', color='green', alpha=0.7, label='LP (linear fit)')
ax1.scatter(weeks, mip_times, s=100, color='blue', zorder=5, label='MIP (actual)', marker='s')
ax1.plot(weeks_smooth, mip_smooth, '--', color='blue', alpha=0.7, label=f'MIP (exp fit, R²={r2:.3f})')
ax1.scatter([29], [mip_pred_29], s=200, color='red', marker='*', zorder=10,
           label=f'29w prediction: {mip_pred_29/3600:.1f}hr')
ax1.set_xlabel('Planning Horizon (weeks)', fontsize=12)
ax1.set_ylabel('Solve Time (seconds)', fontsize=12)
ax1.set_title('LP vs MIP Solve Time Growth', fontsize=14, fontweight='bold')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)
ax1.set_xlim(0, 30)

# Log scale
ax2 = axes[1]
ax2.scatter(weeks, lp_times, s=100, color='green', zorder=5, label='LP (linear)', marker='o')
ax2.plot(weeks_smooth, lp_smooth, '--', color='green', alpha=0.7)
ax2.scatter(weeks, mip_times, s=100, color='blue', zorder=5, label='MIP (exponential)', marker='s')
ax2.plot(weeks_smooth, mip_smooth, '--', color='blue', alpha=0.7)
ax2.scatter([29], [mip_pred_29], s=200, color='red', marker='*', zorder=10,
           label=f'29w: {mip_pred_29/3600:.1f}hr')
ax2.set_xlabel('Planning Horizon (weeks)', fontsize=12)
ax2.set_ylabel('Solve Time (seconds, log scale)', fontsize=12)
ax2.set_title('Performance Growth (Log Scale)', fontsize=14, fontweight='bold')
ax2.set_yscale('log')
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3, which='both')
ax2.set_xlim(0, 30)

plt.tight_layout()
plt.savefig('solver_performance_extrapolation.png', dpi=150)
print(f"\n✅ Saved visualization: solver_performance_extrapolation.png")

print(f"\n{'='*70}")
