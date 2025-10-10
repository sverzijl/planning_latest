\* Source Pyomo model name=unknown *\

min 
ScalarObjective:
+1.0 ONE_VAR_CONSTANT

s.t.

c_e_test1_:
+1 x
-1 y
+1 z
= 10000

c_e_test2_:
+1 x
-1 y
+1 z
= 10000

bounds
   1 <= ONE_VAR_CONSTANT <= 1
   0 <= x <= +inf
   0 <= y <= +inf
   0 <= z <= +inf
end
