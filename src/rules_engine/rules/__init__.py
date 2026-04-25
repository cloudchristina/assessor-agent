from src.rules_engine.rules.r1_sql_login_admin import R1SqlLoginAdmin
from src.rules_engine.rules.r2_dormant_admin import R2DormantAdmin
from src.rules_engine.rules.r3_sod_breach import R3SodBreach
from src.rules_engine.rules.r4_orphaned_login import R4OrphanedLogin
from src.rules_engine.rules.r5_rbac_bypass import R5RbacBypass
from src.rules_engine.rules.r6_shared_account import R6SharedAccount

RULES = [
    R1SqlLoginAdmin(),
    R2DormantAdmin(),
    R3SodBreach(),
    R4OrphanedLogin(),
    R5RbacBypass(),
    R6SharedAccount(),
]
