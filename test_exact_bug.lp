\* Source Pyomo model name=unknown *\

min 
ScalarObjective:
+1.0 ONE_VAR_CONSTANT

s.t.

c_e_inventory_balance(_6122___168846__2025_10_09)_:
+1 inventory(_6122___168846__2025_10_09)
-1 production(2025_10_09__168846_)
+1 truck_load(truck1__168846__2025_10_09)
= 10000.0

c_e_inventory_balance(_6122___168846__2025_10_10)_:
-1 inventory(_6122___168846__2025_10_09)
+1 inventory(_6122___168846__2025_10_10)
-1 production(2025_10_10__168846_)
+1 truck_load(truck1__168846__2025_10_10)
= 0

c_e_inventory_balance(_6122___168847__2025_10_09)_:
+1 inventory(_6122___168847__2025_10_09)
-1 production(2025_10_09__168847_)
+1 truck_load(truck1__168847__2025_10_09)
= 10000.0

c_e_inventory_balance(_6122___168847__2025_10_10)_:
-1 inventory(_6122___168847__2025_10_09)
+1 inventory(_6122___168847__2025_10_10)
-1 production(2025_10_10__168847_)
+1 truck_load(truck1__168847__2025_10_10)
= 0

bounds
   1 <= ONE_VAR_CONSTANT <= 1
   0 <= inventory(_6122___168846__2025_10_09) <= +inf
   0 <= inventory(_6122___168846__2025_10_10) <= +inf
   0 <= inventory(_6122___168847__2025_10_09) <= +inf
   0 <= inventory(_6122___168847__2025_10_10) <= +inf
   0 <= production(2025_10_09__168846_) <= +inf
   0 <= production(2025_10_09__168847_) <= +inf
   0 <= production(2025_10_10__168846_) <= +inf
   0 <= production(2025_10_10__168847_) <= +inf
   0 <= truck_load(truck1__168846__2025_10_09) <= +inf
   0 <= truck_load(truck1__168846__2025_10_10) <= +inf
   0 <= truck_load(truck1__168847__2025_10_09) <= +inf
   0 <= truck_load(truck1__168847__2025_10_10) <= +inf
end
