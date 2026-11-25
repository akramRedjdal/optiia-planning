"""Publication atomique des valeurs, exclusivement dans un onglet dédié existant."""
def publish(df, credentials, spreadsheet_id):
    import gspread
    gc=gspread.service_account_from_dict(credentials,scopes=['https://www.googleapis.com/auth/spreadsheets'])
    book=gc.open_by_key(spreadsheet_id); ws=book.worksheet('Planning E3')
    old=ws.get_all_values(); rows=[list(df.columns)]+df.fillna('').astype(str).values.tolist()
    height=max(len(old),len(rows)); width=max([len(r) for r in old+rows],default=len(df.columns))
    req=[]
    if height>ws.row_count or width>ws.col_count:
        req.append({'updateSheetProperties':{'properties':{'sheetId':ws.id,'gridProperties':{'rowCount':max(height,ws.row_count),'columnCount':max(width,ws.col_count)}},'fields':'gridProperties(rowCount,columnCount)'}})
    req.append({'updateCells':{'range':{'sheetId':ws.id,'startRowIndex':0,'endRowIndex':height,'startColumnIndex':0,'endColumnIndex':width},'rows':[{'values':[{'userEnteredValue':{'stringValue':str(v)}} for v in row]} for row in rows],'fields':'userEnteredValue'}})
    book.batch_update({'requests':req})
    return book.url+'#gid='+str(ws.id)
