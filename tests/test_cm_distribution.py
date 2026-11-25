import unittest
import pandas as pd
from solver import CM, GROUPS, PROGRAM, cm_hours, generate, partial_planning, validate


class CMDistributionTests(unittest.TestCase):
    def setUp(self):
        self.team = [dict(nom=n, groupes=0, distance=True) for n in ('Akram', 'Igor')]
        self.mapping = {}
        for i, group in enumerate(sum(GROUPS.values(), [])):
            name = f'Enseignant {i}'
            self.team.append(dict(nom=name, groupes=1, distance=True))
            self.mapping[group] = name
        self.team.append(dict(nom='B3', groupes=1, distance=True))
        rows = []
        for offset, block in enumerate(GROUPS):
            for k in range(15):
                date = (pd.Timestamp('2027-03-01') + pd.Timedelta(days=2*k+offset)).strftime('%Y-%m-%d')
                rows.append(dict(bloc=block, date=date, heure=8, distance=False, controle=False, id=date+' 08:00'))
        self.available = pd.DataFrame(rows)

    def test_complete_both_orders_and_legacy(self):
        for first, second in [('Akram', 'Igor'), ('Igor', 'Akram'), ('Akram', 'Akram')]:
            with self.subTest(first=first, second=second):
                owners = {b: {PROGRAM[k]: first if i < 2 else second for i, k in enumerate(CM)} for b in GROUPS}
                if first == second:
                    owners = {b: first for b in GROUPS}
                df, message = generate(self.team, owners, self.mapping, available=self.available)
                self.assertIsNotNone(df, message)
                self.assertEqual(validate(df, self.team, owners, self.mapping, available=self.available), [])
                for course, teacher in [('COURS 1', first), ('COURS 2', first), ('COURS 3', second), ('COURS 4', second)]:
                    self.assertEqual(set(df.loc[df['Séance'] == course, 'Intervenant']), {teacher})
                self.assertEqual(cm_hours(owners, first), 16 if first == second else 8)
                wrong = df.copy()
                wrong.loc[wrong['Séance'] == 'COURS 1', 'Intervenant'] = second if first != second else 'Igor'
                self.assertIn('CM incorrect', validate(wrong, self.team, owners, self.mapping, available=self.available))

    def test_partial_respects_teacher_and_unavailability(self):
        owners = {b: {PROGRAM[k]: 'Akram' if i < 2 else 'Igor' for i, k in enumerate(CM)} for b in GROUPS}
        blocked = [('Akram', self.available.iloc[0].id)]
        df, mapping, _, message = partial_planning(self.team, owners, b3='B3', blocked=blocked, available=self.available, seconds=5)
        self.assertIsNotNone(df, message)
        self.assertFalse(((df.Intervenant == 'Akram') & (df.Date+' '+df['Début'] == blocked[0][1])).any())
        errors = validate(df, self.team, owners, mapping, blocked, self.available)
        self.assertFalse([e for e in errors if not e.startswith('Couverture/ordre : ')], errors)
        for row in df[df.Type == 'CM'].to_dict('records'):
            self.assertEqual(row['Intervenant'], owners[row['Bloc']][row['Séance']])


if __name__ == '__main__':
    unittest.main()
