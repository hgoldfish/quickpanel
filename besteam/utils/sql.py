import os
import sqlite3
import threading
import pickle
import traceback
import types
import sys
import warnings
import logging
import functools
try:
    from PyQt5.QtCore import QDate, QDateTime, QObject
    usingPyQt5 = True
except ImportError:
    usingPyQt5 = False

__all__ = ["Table", "Database", "DatabaseException", "transaction", "DataObject",
    "DataObjectProxy", "createDataObject", "createDetachedDataObject"]

#是否打印调试信息，如果为真，会打印出所有执行的SQL语句
sql_debug = False
logger = logging.getLogger(__name__)


def pickle_dumps(o):
    return pickle.dumps(o, 2)
    
def pickle_loads(s):
    return pickle.loads(s)

class DictProxy:
    def setTarget(self, dataObject):
        self.__target = dataObject

    def target(self):
        return self.__target

    def __setitem__(self, k, v):
        self.__target[k] = v

    def __getitem__(self, k):
        return self.__target[k]

    def __delitem__(self, k):
        del self.__target[k]

    def get(self, k, default = None):
        try:
            return self.__getitem__(k)
        except KeyError:
            return default

    def update(self, d):
        if __debug__:
            if self.__setitem__.__func__ is not DictProxy.__setitem__.__func__ \
                    and self.update.__func__ is DictProxy.update.__func__:
                warnings.warn("是不是忘了重载DictProxy.update()")
        self.__target.update(d)

    def copy(self):
        return self.__target.copy()

    def __len__(self):
        return len(self.__target)

    def items(self):
        return self.__target.items()

    def keys(self):
        return self.__target.keys()

    def values(self):
        return self.__target.values()

    def __contains__(self, k):
        return k in self.__target

def classNameToSqlName(className):
    """把表格的类名转换成表格的SQL表名。如`ClassName`到`class_name`"""
    return className[0].lower() + "".join(
            c if c.islower() else "_" + c.lower() for c in className[1:])

#让sqlite3认识QDateTime
def adapt_QDateTime(d):
    return d.toTime_t()

def convert_QDateTime(t):
    return QDateTime.fromTime_t(int(t))

def adapt_QDate(d):
    return d.toJulianDay()

def convert_QDate(t):
    return QDate.fromJulianDay(int(t))

def adapt_bool(b):
    return 'T' if b else 'F'

def convert_bool(b):
    return b == b"T"

if usingPyQt5:
    sqlite3.register_adapter(QDateTime, adapt_QDateTime)
    sqlite3.register_adapter(QDate, adapt_QDate)
sqlite3.register_adapter(bool, adapt_bool)
sqlite3.register_adapter(list, pickle_dumps)
sqlite3.register_adapter(dict, pickle_dumps)
if usingPyQt5:
    sqlite3.register_converter("QDateTime", convert_QDateTime)
    sqlite3.register_converter("QDate", convert_QDate)
sqlite3.register_converter("bool", convert_bool)
sqlite3.register_converter("list", pickle.loads)
sqlite3.register_converter("dict", pickle.loads)

transaction_local = threading.local()
__transaction_debug = False

def transaction(wrapped):
    "标注某个函数是形成一个事务，可以嵌套，但是不形成子事务。"
    def wrapper(*l, **d):
        passed = False
        try:
            if hasattr(transaction_local, "transaction") or __transaction_debug:
                passed = True
            else:
                transaction_local.transaction = True
                transaction_local.conn = None
            result = wrapped(*l, **d)
            if not passed and transaction_local.conn is not None:
                transaction_local.conn.commit()
            return result
        except:
            if not passed and transaction_local.conn is not None:
                try:
                    transaction_local.conn.rollback()
                except:
                    if __debug__:
                        traceback.print_exc()
            raise
        finally:
            if not passed:
                del transaction_local.transaction
                del transaction_local.conn
    functools.update_wrapper(wrapper, wrapped)
    return wrapper


class DatabaseException(Exception):
    pass


class InvalidTableException(DatabaseException):
    pass


#DataObject是一个简单的东西。它并不能处理关系映射之类的东西。它不是什么ORM。
#TODO 通过Database.update()语句更新数据库时没有判断数据对象需不需要更新。
#这种情况可能会产生一些不一致现象。现在的原则是，使用数据对象就不使用update()
class DataObject(DictProxy):
    """数据对象用于存取数据库记录，它的使用形式类似于Python内置的dict类型。
    DataObject本质是一个容纳数据库记录的缓存，但是可以设定某个字段不读取到内存中。
    使用__setitem__()时，如果字段是数据库字段，该数值会立即保存到数据库内。
    字段不是数据库字段，该数值会保存到缓存内，可以使用__getitem__取出这个数值
    提供了一个deleteFromDatabase()函数用于从数据库中删除此条记录。
    除了可以通过__getitem__()获得数据库字段，还有以下五个属性：
    DataObject.id 主键的值
    DataObject.table 数据对象所属的表格的Python类对象。
    DataObject.db 数据对象所属的Database
    DataObject.detached 数据对象是否处于分离状态
    DataObject.notInMemory 这个是一个列表，用于指明哪些字段不处于内存中
    数据对象有两种状态————与数据库关联或者从数据库分离。当它处于与数据库关联的状态时，
    使用__setitem__()或者update()设置的字段值会立即更新到数据库内。
    当它处于分离状态时，字段值只会保存在缓存内。可以使用attach()方法将分离状态转变为
    关联状态。调用attach()之后，处于缓存内的数据值会立即更新到数据库。
    有时某些字段的值比较大，可能是一篇文章或者一个图像。这种字段不适宜放在缓存中。
    可以将它的字段名加入到DataObject.notInMemory列表内。
    """

    def __init__(self, id, table, db, record = None):
        self.id, self.table, self.db = id, table, db
        #如果detached为True，使用数据对象的__setitem__更新数据的时候，数据不会直接更新到数据库中
        self.detached = False
        self.notInMemory = []
        self.convertors = {}
        if record is None:
            self.reload()
        else:
            self.setTarget(record)

    def __repr__(self):
        return "DataObject" + ("(detached):" if self.detached else ":") + repr(self.target())

    def __getitem__(self, k):
        if k in self.notInMemory and not self.detached:
            cursor = self.db.conn().cursor()
            sql = "select %s from %s where %s=?;" % (k, self.table.getName(), self.table.getPkName())
            id = self.target()[self.table.getPkName()]
            if sql_debug:
                print(sql, "id=", id)
            cursor.execute(sql, (id, ))
            row = cursor.fetchone()
            if row is None:
                raise KeyError
            v = row[0]
            if sys.version_info[0] < 3 and isinstance(v, buffer):
                v = bytes(v)
        else:
            v = DictProxy.__getitem__(self, k)
        if k in self.convertors:
            return self.convertors[k](v)
        return v

    @transaction
    def __setitem__(self, k, v):
        #一个小的优化，如果新值与旧值一样，就不写数据库
        changed = True
        if k not in self.notInMemory: # and not self.detached
            if k in self.target():
                #有时候升级数据库的时候，旧的字段类型可能会和新的字段类型不一样。
                changed = (type(self.target()[k] is not type(v) or self.target()[k] != v))
            self.target()[k] = v
        if not self.detached and changed:
            #实际上并不一定会更新，Database.update()会判断字段是不是数据库的字段
            self.db.update(self.table.getName(), {k:v, "__reload_cache":False}, \
                    "where %s=?" % self.table.getPkName(), self.id)

    @transaction
    def update(self, d):
        d = d.copy()
        self.target().update(d)
        if not self.detached:
            for field in self.notInMemory:
                try:
                    del self.target()[field]
                except KeyError:
                    pass
            d["__reload_cache"] = False
            self.db.update(self.table.getName(), d, "where %s=?" % self.table.getPkName(), self.id)

    @transaction
    def deleteFromDatabase(self):
        "从数据库中删除此纪录。"
        if self.detached:
            return
        self.db.delete(self.table.getName(), "where %s=?" % self.table.getPkName(), self.id)
        self.detached = True

    def reload(self):
        "重新载入所有数据。如果原来定义了notInMemory，最好不要使用reload()，会导致所有数据载入内存"
        #目前，用到这个函数并不多。这个函数原来设计为让数据库自动刷新缓存的。但是dolphin都是一些简单
        #的CRUD，根本用不到那些复杂的功能。
        if self.detached:
            return
        rows = self.db.select(self.table.getName(), "where %s=?" % self.pk, self.id)
        assert len(rows) == 1
        self.setTarget(rows[0])

    def copy(self):
        "返回一个dict，内容是该条记录，包含self.notInMemory内的字段"
        d = self.target().copy()
        #TODO 优化一下，一次性把所有在notInMemory的字段取出来。不是很重要，因为目前大多数表格只有一个notInMemory字段。
        if not self.detached:
            for k in self.notInMemory:
                d[k] = self.__getitem__(k)
        #支持convertor
        for name, convertor in self.convertors.items():
            d[name] = convertor(d[name])
        return d

    def attach(self):
        "关联到数据库。把数据插入数据库。"
        if not self.detached:
            return
        self.db.insert(self.table.getName(), self.target())
        for field in self.notInMemory:
            try:
                del self.target()[field]
            except KeyError:
                pass
        self.detached = False

def createDataObject(dataObjectNameOrClass, db, record):
    """创建一个数据对象，除了本模块外，通常不直接使用DataObject的构造函数
    参数dataObjectName是数据对象的名字，比如DiaryDay之类的。或者直接可以是类型
    db是数据对象从属的数据库,record则是数据对象的值"""
    if type(dataObjectNameOrClass) is types.ClassType and\
            issubclass(dataObjectNameOrClass, Table):
        table = dataObjectNameOrClass
    else:
        assert isinstance(dataObjectNameOrClass, str)
        table = db.getTableByClassName(dataObjectNameOrClass)
    assert table is not None
    id = record[table.getPkName()]
    return DataObject(id, table, db, record)

def createDetachedDataObject(dataObjectNameOrClass, db, record):
    """一个方便使用的小类。与createDataObject()类型。但是返回的类型没有关联到数据库。
    修改数据时不会更新到数据库。"""
    do = createDataObject(dataObjectNameOrClass, db, record)
    do.detached = True
    return do

class DataObjectProxy(DictProxy):
    """如果一个类想要基于DataObject实现dict的接口，可以继承这个类型。
    不直接继承DataObject，因为它不是一种 is 关系。"""

    def deleteFromDatabase(self):
        self.target().deleteFromDatabase()

    def reload(self):
        self.target().reload()

    def setTarget(self, target):
        assert isinstance(target, DataObject)
        DictProxy.setTarget(self, target)

if usingPyQt5:
    _QObject = QObject
else:
    class _QObject:
        def __init__(self):
            pass

        def trUtf8(self, utf8Bytes):
            return utf8Bytes.decode("utf-8")

#继承于QObject的主要原因是为了使用self.tr()
class Database(_QObject):
    @transaction
    def __init__(self, dbfile):
        _QObject.__init__(self)
        self.dbfile = dbfile
        conn = self.conn()
        cursor = conn.cursor()
        #首先创建表格。创建表格的时候使用createInitialData()方法填充基本数据。
        if not os.path.exists(dbfile):
            for table in self.tables:
                sql = table.getCreateStatement()
                if sql_debug:
                    print(sql)
                cursor.execute(sql)
                self.createInitialData(table)
        else:
            #如果数据库已经存在。从sqlite_master中读取现存表格的名字。如果有表格尚未存在，就创建它。
            #并使用createInitialData()填充基本数据
            cursor.execute("select name from sqlite_master where type='table';")
            tables = [row[0].lower() for row in cursor.fetchall()]
            for table in self.tables:
                if table.getName().lower() not in tables:
                    sql = table.getCreateStatement()
                    if sql_debug:
                        print(sql)
                    cursor.execute(sql)
                    self.createInitialData(table)
        #接下来创建索引。因为创建索引与创建表格不一样，不需要填充基本数据，所以使用if not exists语句。每次
        #都用SQL创建一遍。
        for table in self.tables:
            sql = "create unique index if not exists {pkName}_idx on {tableName} ({pkName});"
            sql = sql.format(pkName = table.getPkName(), tableName = table.getName())
            if sql_debug:
                print(sql)
            cursor.execute(sql)
            if not hasattr(table, "indexes"):
                continue
            for index in table.indexes:
                if isinstance(index, str):
                    sql = "create index if not exists {columnName}_idx on {tableName} ({columnName});"
                    sql = sql.format(columnName = index, tableName = table.getName())
                elif isinstance(index, (tuple, list)):
                    sql = "create index if not exists {columnNames1}_idx on {tableName} ({columnNames2});"
                    columnNames1 = "_".join(index)
                    columnNames2 = ",".join(index)
                    sql = sql.format(columnNames1 = columnNames1, columnNames2 = columnNames2, tableName = table.getName())
                if sql_debug:
                    print(sql)
                cursor.execute(sql)


    def createInitialData(self, table):
        "一个虚拟函数，用于创建数据初始值，参数table是表的类型(派生于Table)"
        pass

    def conn(self):
        if hasattr(transaction_local, "transaction") and \
                transaction_local.transaction:
            if transaction_local.conn is None:
                transaction_local.conn = sqlite3.connect(self.dbfile, \
                        detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
                transaction_local.conn.row_factory = sqlite3.Row
                transaction_local.conn.isolation_level = "DEFERRED"
            conn = transaction_local.conn
        else:
            conn = sqlite3.connect(self.dbfile, \
                    detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn.row_factory = sqlite3.Row
            conn.isolation_level = None
        return conn

    def __getattr__(self, attrname):
        def wrapper(boundMethod, tableName):
            def func(*args, **dictArgs):
                try:
                    return boundMethod(tableName, *args, **dictArgs)
                except Exception as e:
                    if __debug__:
                        traceback.print_exc()
                    if not isinstance(e, DatabaseException):
                        raise DatabaseException(e)
                    else:
                        raise e
            func.__name__ = boundMethod.__name__
            return func

        for method in ["select", "update", "delete", "insert"]:
            if attrname.startswith(method):
                if method == "select" and attrname.endswith("Ids"):
                    tableClassName = attrname[len(method): - 3]
                    method = "selectIds"
                else:
                    tableClassName = attrname[len(method):]
                table = self.getTableByClassName(tableClassName)
                boundMethod = getattr(self, method)
                return wrapper(boundMethod, table.getName())
        raise AttributeError(attrname)

    def extractObject(self, cursor, table):
        "从cursor内读取数据对象，返回一列DataObject的list"
        resultset = []
        columns = [e[0] for e in cursor.description]
        for row in cursor:
            record = {}
            for column in columns:
                #在Python2.6版本中column是bytes类型，并且sqlite3.Row.__getitem__()只接收bytes类型的参数
                value = row[column]
                if sys.version_info[0] < 3 and isinstance(value, buffer):
                    value = bytes(value)
                record[str(column)] = value
            id = record[table.getPkName()]
            dataObject = DataObject(id, table, self, record)
            resultset.append(dataObject)
        return resultset

    def adoptTypes_List(self, parameters):
        """很多函数接受list类型的参数。因为sqlite3 for python 2.x需要buffer类型的blob，
        所以这里对参数进行处理。使之兼容2.x与3.x版本。"""
        parameters2 = []
        for parameter in parameters:
            if sys.version_info[0] < 3 and isinstance(parameter, bytes):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    parameter = buffer(parameter)
            parameters2.append(parameter)
        return parameters2

    def adoptTypes_Dict(self, record):
        """很多函数接受dict类型的参数。因为sqlite3 for python 2.x需要buffer类型的blob，
        所以这里对参数进行处理。使之兼容2.x与3.x版本。"""
        record2 = {}
        for field, value in record.items():
            if sys.version_info[0] < 3 and isinstance(value, bytes):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    value = buffer(value)
            record2[field] = value
        return record2

    def select(self, tableName, sql, *parameters):
        "使用select语句从数据库中取得数据。返回DataObject的列表。"
        if sql != "":
            sql = "select %s from %s " + sql + ";"
        else:
            sql = "select %s from %s;"
        table = self.getTableBySqlName(tableName)
        columns = ",".join(table.getColumnNames())
        parameters = self.adoptTypes_List(parameters)
        cursor = self.conn().cursor()
        if sql_debug:
            print(sql % (columns, tableName), repr(parameters))
        cursor.execute(sql % (columns, tableName), parameters)
        return self.extractObject(cursor, table)

    def selectIds(self, tableName, sql, *parameters):
        "使用select语句从数据库中取得数据的ID列表。"
        if sql != "":
            sql = "select %s from %s " + sql + ";"
        else:
            sql = "select %s from %s;"
        table = self.getTableBySqlName(tableName)
        parameters = self.adoptTypes_List(parameters)
        cursor = self.conn().cursor()
        if sql_debug:
            print(sql % (table.getPkName(), tableName), repr(parameters))
        cursor.execute(sql % (table.getPkName(), tableName), parameters)
        ids = []
        #Python2.6的sqlite3.Row.__getitem__()只接受bytes类型的参数
        if sys.version_info[0] < 3:
            for row in cursor:
                ids.append(row[bytes(table.getPkName())])
        else:
            for row in cursor:
                ids.append(row[table.getPkName()])
        return ids

    def update(self, tableName, row, sql, *parameters):
        "使用update更新数据库表。"
        if sql != "":
            sql = "update %s set %s " + sql + ";"
        else:
            sql = "update %s set %s;"

        table = self.getTableBySqlName(tableName)
        parameters = self.adoptTypes_List(parameters)
        row = self.adoptTypes_Dict(row)
        keys = []
        values = []
        for key, value in row.items():
            if key not in table.getColumnNames():
                continue
            keys.append(key)
            values.append(value)
        if len(keys) == 0:
            return
        values.extend(parameters)

        columns = ",".join([column + "=?" for column in keys])
        conn = self.conn()
        cursor = conn.cursor()
        if sql_debug:
            print(sql % (tableName, columns), repr(values))
        cursor.execute(sql % (tableName, columns), values)

    def delete(self, tableName, sql, *parameters):
        "从数据库中删除数据。一般用deleteTableName()的形式调用。"
        if sql != "":
            sql = "delete from %s " + sql + ";"
        else:
            sql = "delete from %s;"
        parameters = self.adoptTypes_List(parameters)
        conn = self.conn()
        cursor = conn.cursor()
        if sql_debug:
            print(sql % tableName, repr(parameters))
        cursor.execute(sql % tableName, parameters)

    def insert(self, tableName, row2): #等下要返回DataObject，所以改名row2
        "把数据添加到数据库中。参数是一个dict类型，其中包含了一条纪录。"
        table = self.getTableBySqlName(tableName)
        sql = "insert into %s (%s) values (%s);"
        row = self.adoptTypes_Dict(row2)
        keys = []
        values = []
        for key, value in row.items():
            if key not in table.getColumnNames():
                continue
            keys.append(key)
            values.append(value)
        if len(keys) == 0:
            return

        columns = ",".join(keys)
        questions = ",".join("?" * len(keys))
        conn = self.conn()
        cursor = conn.cursor()
        if sql_debug:
            print(sql % (tableName, columns, questions), repr(values))
        cursor.execute(sql % (tableName, columns, questions), values)
        return DataObject(row[table.getPkName()], table, self, row2)

    @classmethod
    def getTableBySqlName(cls, tableName):
        "根据表格的数据库名返回表格的Python类型。"
        for table in cls.tables:
            if table.getName() == tableName:
                return table
        raise InvalidTableException(tableName)

    @classmethod
    def getTableByClassName(cls, tableClassName):
        "根据表格的类名返回表格的Python类型。"
        for table in cls.tables:
            if table.__name__ == tableClassName:
                return table
        raise InvalidTableException(tableClassName)

class Table:
    "用于定义表格的基础类型。"

    @classmethod
    def getName(cls):
        """返回表名，此处的表名是指在数据库内的表名
        在继承Table的时候可以定义tableName属性。getName()会返回这个属性的值
        如果没有，则使用classNameToSqlName的规则转换类名为表名"""
        if hasattr(cls, "tableName"):
            return cls.tableName
        tableName = classNameToSqlName(cls.__name__)
        return tableName

    @classmethod
    def getColumnNames(cls):
        return cls.columns.keys()

    @classmethod
    def getCreateStatement(cls):
        tableName = cls.getName()
        columnDefination = ",".join([name + " " + type for name, type in cls.columns.items()])
        sql = "create table %s (%s);" % (tableName, columnDefination)
        #sql2="create index if not exists %s on %s ()"
        #FIXME 为pk增加unique属性
        return sql

    @classmethod
    def getPkName(cls):
        """返回表格的主键名，一般是"id"，但是子类也可以定义pkName属性"""
        if hasattr(cls, "pkName"):
            return cls.pkName
        return "id"

    @classmethod
    def getIndexes(cls):
        "返回表格定义的索引"
        return cls.indexes


if __name__ == "__main__":
    class Person(Table):
        pkName = "name"
        columns = {"name":"text", "age":"integer", "sex":"text"}

    class MyDatabase(Database):
        tables = (Person, )

    db = MyDatabase("test.dat")
    db.insertPerson({"name":"goldfish", "age":25, "sex":"M", "test":"none"})
    db.insertPerson({"name":"kaola", "age":26, "sex":"M", "test":"haha"})
    print(db.selectPerson(""))
    db.deletePerson("where name=?", "goldfish")
    db.updatePerson({"age":27, "newtest":"okay"}, "where name=?", "kaola")
    print(db.selectPerson(""))

