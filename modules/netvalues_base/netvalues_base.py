import os
import database_assistant.DatabaseAssistant as da

class netvalues_base:
    """ 从已存储到数据库的估值表中，提取信息并计算净值的类 """
    def __init__(self,dbdirbase,netdbdirbase,pname,pnickname):
        self._dbdir = os.path.join(dbdirbase,''.join(['rawdb_',pnickname,'.db']))               # 存储估值表信息的数据库
        self._netdbdir = os.path.join(netdbdirbase,''.join(['netdb_',pnickname,'.db']))             # 存储净值信息的数据库
        self._product_name = pname  # 产品中文名称
        self._product_nickname = pnickname # 产品英文名称

    def get_newtables(self):
        """
        提取已存储至数据库但还未处理 的 估值表的名称（数据库标准名称格式：产品代码_产品名称_日期）
        """
        with da.DatabaseAssistant(dbdir=self._dbdir) as db:
            temp = db.get_db_tablenames()
            temp.remove('SAVED_TABLES')
            savedtbs = set(temp)
        with da.DatabaseAssistant(dbdir=self._netdbdir) as netdb:
            cursor = netdb.connection.cursor()
            netdb.create_db_table(tablename='PROCESSED_TABLES',titles=['TableNames TEXT'],replace=False)
            temp = cursor.execute('SELECT * FROM PROCESSED_TABLES')
            processedtbs = set([tb[0] for tb in temp])
        newtables=sorted(list(savedtbs.difference(processedtbs)))
        return newtables

    def table_to_netdb(self,tablename,codedict,indexmark='科目代码',defaultvalcols=('市值','市值本币')):
        """
        从已经存储到数据库中的估值表中提取计算净值所需的基础元素，更新至netdb中
        更新前需检查 PROCESSED_TABLES 中是否已经拥有了该表格，已经存在的话就不能写入，报错
        tablename 为需要更新的表格名称 在估值表数据库中的名称 标准名称
        codedict 为存储必须提取的行的字典，如果估值表中没有该行的话则其值应该为零
        indexmark 为行标记，标记存储codedict需要提取的字段的列
        valcols 可能作为存储数值的列的名称通常为 [市值 、市值本币]
        """
        # 从数据库中的估值表中提取需要的字段的值，并赋予标准化名称
        if not codedict:
            print('[-]Codedict is empty can not update table : %s' % tablename)
        output_dict = {} # 存储提取出的数值的字典
        rev_codedict = {} # 以行名(indexmark列对应的值)为KEY
        valcols = [indexmark]
        for cd in codedict:  # 初始化输出字典
            output_dict[cd] = 0
            cditem = codedict[cd]
            if len(cditem)>1:
                valcols.append(cditem[1])   # 把非默认的列提取出来
                rev_codedict[cditem[0]] = (cd,cditem[1])
            else:
                rev_codedict[cditem[0]] = (cd,)
        #rev_codedict = {v[0]:k for k,v in codedict.items()}   # 以行名为KEY，对应要素表列名为值的字典
        # 提取数据
        with da.DatabaseAssistant(self._dbdir) as db:
            cols = db.get_table_cols(tablename)
            # 匹配用作存储的值，同一只产品有些会是市值 、有些市值本币 所以需要逐一匹配
            valmark = None
            for col in defaultvalcols:
                if col in cols:
                    valmark = col
                    break
            if not valmark:
                raise Exception('[-]在表格 %s 中没有匹配到存储数值的列' %tablename)
            else:
                valcols.insert(1,valmark)
            cursor = db.connection.cursor()
            exeline=''.join(['SELECT ',','.join(valcols),' FROM ',tablename])
            rowvals = cursor.execute(exeline).fetchall()  # 提取 indexmark 列对应的值
            for row in rowvals:
                rowname = row[0].strip()
                if rowname in rev_codedict:
                    item = rev_codedict[rowname]
                    itemcol = item[1] if len(item)>1 else valmark
                    output_dict[item[0]] = row[valcols.index(itemcol)]
        # 写入 netdb 元素表
        filedate = tablename[-8:]
        with da.DatabaseAssistant(self._netdbdir) as netdb:
            base_titles = ['date TEXT']
            base_values = [filedate]
            for cd in sorted(output_dict):
                base_titles.append(' '.join([cd,'REAL']))
                base_values.append(output_dict[cd])
            netdb.create_db_table(tablename='Net_Values_Base',titles=base_titles,replace=False)
            try: # 开始写入净值基础数据
                cursor = netdb.connection.cursor()
                exeline = ''.join(['INSERT INTO Net_Values_Base VALUES (',','.join(['?']*len(base_titles)),')' ])
                cursor.execute(exeline,tuple(base_values))
                netdb.connection.commit()
            except:
                print('[-]Update Net_Values_Base with table %s failed !' %tablename)
                raise
            else:
                cursor.execute('INSERT INTO PROCESSED_TABLES VALUES (?)',(tablename,))  # 需要一个 tuple 作为输入
                netdb.connection.commit()
                print('[+]Update Net_Values_Base with table %s succed !' %tablename)

    def update_netdb(self,codedict,indexmark='科目代码',defaultvalcols=('市值','市值本币')):
        """ 将所有需要更新的表格的基础元素逐一写入数据库 """
        if not codedict:    # 没有提供codedict
            print('[-]No codedict provided,not updating')
            return
        newtables = self.get_newtables()  # 提取还未更新的表格的列表
        if newtables:
            for tablename in newtables:
                self.table_to_netdb(tablename=tablename,codedict=codedict,indexmark=indexmark,defaultvalcols=defaultvalcols)
            print('[+]Updated Net_Values_Base from %s to %s ' %(newtables[0][-8:],newtables[-1][-8:]))
        else:
            print('[+]Netval_db already update to the latest !')

    def check_dupicate_netdb(self):
        """ 检查表格中是否有重复日期 """
        pass
