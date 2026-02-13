import json
import math
import copy
from pathlib import Path


TEMPLATE_FILE = Path(__file__).parent / "templates.json"


def load_templates(path=TEMPLATE_FILE):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_templates(data, out_path):
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def compute_D(template):
    damages = []
    for a in template.get('actions', []):
        if a.get('action_type') == 'Attack' and 'damage' in a:
            damages.append(a['damage'])
    if not damages:
        return 0.0
    return sum(damages) / len(damages)


def formula_A_linear(templates, weights=(0.4, 0.4, 0.2), P_t=1.0):
    # refs: mean values across templates
    H = [t['maxHP'] for t in templates]
    D = [compute_D(t) for t in templates]
    M = [t.get('movement', 0) for t in templates]
    H_ref = max(1, sum(H) / len(H))
    D_ref = max(1, sum(D) / len(D))
    M_ref = max(1, sum(M) / len(M))

    out = copy.deepcopy(templates)
    w_h, w_d, w_m = weights
    for t in out:
        HP = t['maxHP']
        Dv = compute_D(t)
        Mv = t.get('movement', 0)
        h = HP / H_ref
        d = Dv / D_ref if D_ref else 0
        m = Mv / M_ref if M_ref else 0
        P = w_h * h + w_d * d + w_m * m
        s = P_t / P if P > 0 else 1.0
        # scale all stats uniformly
        t['maxHP'] = max(1, int(round(HP * s)))
        t['curHP'] = min(t.get('curHP', t['maxHP']), t['maxHP'])
        # scale damages
        for a in t.get('actions', []):
            if a.get('action_type') == 'Attack' and 'damage' in a:
                a['damage'] = max(0, round(a['damage'] * s, 2))
        # scale movement but keep int
        t['movement'] = max(1, int(round(Mv * s)))
    return out


def formula_B_log(templates, weights=(0.4, 0.4, 0.2), P_t=1.0):
    w_h, w_d, w_m = weights
    out = copy.deepcopy(templates)
    for t in out:
        HP = t['maxHP']
        Dv = compute_D(t)
        Mv = t.get('movement', 0)
        P_current = w_h * math.log(1 + HP) + w_d * math.log(1 + Dv) + w_m * math.log(1 + Mv)
        # Solve for HP that reaches P_t keeping D and M fixed:
        numerator = P_t - w_d * math.log(1 + Dv) - w_m * math.log(1 + Mv)
        if w_h == 0:
            HP_new = HP
        else:
            HP_new = math.exp(numerator / w_h) - 1
        HP_new = max(1, int(round(HP_new)))
        t['maxHP'] = HP_new
        t['curHP'] = min(t.get('curHP', HP_new), HP_new)
    return out


def formula_C_multiplicative(templates, alpha=1.0, beta=1.0, gamma=0.1, P_t=1.0):
    out = copy.deepcopy(templates)
    # compute current P for each and scale HP to reach P_t (keep D and M fixed)
    for t in out:
        HP = t['maxHP']
        Dv = compute_D(t)
        Mv = t.get('movement', 0)
        P_cur = (HP ** alpha) * (max(1e-6, Dv) ** beta) * (1 + gamma * Mv)
        if P_cur <= 0:
            s = 1.0
        else:
            s = (P_t / P_cur) ** (1.0 / alpha)
        HP_new = max(1, int(round(HP * s)))
        t['maxHP'] = HP_new
        t['curHP'] = min(t.get('curHP', HP_new), HP_new)
    return out


def summarize(old, new):
    lines = []
    for o, n in zip(old, new):
        lines.append({
            'name': o.get('display_name'),
            'old_HP': o.get('maxHP'),
            'new_HP': n.get('maxHP'),
            'old_D': compute_D(o),
            'new_D': compute_D(n),
            'old_M': o.get('movement'),
            'new_M': n.get('movement'),
        })
    return lines


def main():
    data = load_templates()
    templates = data.get('templates', [])

    A = formula_A_linear(templates, weights=(0.45, 0.4, 0.15), P_t=1.0)
    B = formula_B_log(templates, weights=(0.4, 0.4, 0.2), P_t=1.0)
    C = formula_C_multiplicative(templates, alpha=1.2, beta=1.0, gamma=0.15, P_t=1.0)

    save_templates({'templates': A}, Path(__file__).parent / 'templates_A.json')
    save_templates({'templates': B}, Path(__file__).parent / 'templates_B.json')
    save_templates({'templates': C}, Path(__file__).parent / 'templates_C.json')

    print('Summary A (linear):')
    for s in summarize(templates, A):
        print(s)
    print('\nSummary B (log):')
    for s in summarize(templates, B):
        print(s)
    print('\nSummary C (multiplicative):')
    for s in summarize(templates, C):
        print(s)


if __name__ == '__main__':
    main()
