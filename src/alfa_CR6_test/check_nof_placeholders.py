# coding: utf-8


def check_nof_placeholders(D):
    cntr = 1
    for k, v in D.items():
        if k.count('{}') != v.count('{}'):
            print(f"[{cntr}] {k.count('{}')} != {v.count('{}')}")
            print(f"   k:{k}")
            print(f"   v:{v}")
            print("=================")
            cntr += 1
