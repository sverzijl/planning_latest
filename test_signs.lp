\* Source Pyomo model name=unknown *\

min 
ScalarObjective:
+1.0 ONE_VAR_CONSTANT

s.t.

c_e_method1_con_:
+1 inventory
-1 production
+1 truck1
+1 truck2
= 10000

bounds
   1 <= ONE_VAR_CONSTANT <= 1
   0 <= inventory <= +inf
   0 <= production <= +inf
   0 <= truck1 <= +inf
   0 <= truck2 <= +inf
end
