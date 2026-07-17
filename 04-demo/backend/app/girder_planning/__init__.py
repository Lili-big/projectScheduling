"""架梁专项领域能力。

领域服务只负责确定性的产存运架、归属、通行和倒排计算；综合任务生成、
CP-SAT 求解和计划发布分别由适配器、联合编排器与计划管控服务负责。
"""

from .fingerprints import stable_fingerprint, stable_id

__all__ = ["stable_fingerprint", "stable_id"]
