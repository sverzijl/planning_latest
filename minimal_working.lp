\* Source Pyomo model name=unknown *\

min 
x1:
+5.03125 x2
+5.03125 x3
+1 x4
+10000.0 x5

s.t.

c_e_x6_:
-1 x2
+1 x4
+1 x7
= 0

c_e_x8_:
-1 x4
+1 x9
-1 x10
+1 x11
= 0

c_e_x12_:
-1 x7
+1 x13
= 0

c_e_x14_:
+1 x10
= 0

c_e_x15_:
+1 x16
+1 x17
= 0

c_e_x18_:
-1 x3
+1 x19
= 0

c_e_x20_:
+1 x5
+1 x11
+1 x17
= 100.0

c_u_x21_:
-1 x9
+1 x11
<= 0

c_u_x22_:
-1 x16
+1 x17
<= 0

c_u_x23_:
+1 x2
<= 12000.0

c_u_x24_:
+1 x3
<= 12000.0

bounds
   0 <= x2 <= +inf
   0 <= x3 <= +inf
   0 <= x4 <= +inf
   0 <= x5 <= +inf
   0 <= x7 <= +inf
   0 <= x9 <= +inf
   0 <= x13 <= +inf
   0 <= x10 <= +inf
   0 <= x16 <= +inf
   0 <= x19 <= +inf
   0 <= x11 <= +inf
   0 <= x17 <= +inf
end
