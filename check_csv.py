import pandas as pd

path = 'page_metrics.csv'

print('opening', path)
df = pd.read_csv(path, comment='#')
print(df.columns)
print(df.head())
