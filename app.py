import json
from flask import Flask, render_template, jsonify, request
from xml.etree import ElementTree as ET
import requests
import psycopg2
from flask_sqlalchemy import SQLAlchemy
import config
from concurrent.futures import ProcessPoolExecutor

app = Flask(__name__)

app.config.from_object(config.DevelopmentConfig())
db = SQLAlchemy(app)


class AddressInfo(db.Model):
    __tablename__ = "address_codes"
    # __table_args__ = {"mysql_collate": "utf8_general_ci"}

    code = db.Column(db.String(10), primary_key=True)
    address_name = db.Column(db.String(128))
    parent_code = db.Column(db.String(5))
    updated_at = db.Column(db.DateTime, server_default=db.func.now())

    price_info = db.relationship("TradeInfo", backref="address_codes", lazy=True)

    def __repr__(self):
        return "code = %s, name = %s, parent_code=%s, updated_at = %s" % (
            self.code,
            self.address_name,
            self.parent_code,
            self.updated_at,
        )

    @property
    def serialize(self):
        return {
            "code": self.code,
            "address_name": self.address_name,
            "parent_code": self.parent_code,
            "updated_at": self.updated_at,
        }


class TradeInfo(db.Model):
    __tablename__ = "trade_info"
    # __table_args__ = {"mysql_collate": "utf8_general_ci"}
    id = db.Column(db.Integer, primary_key=True)
    serial_no = db.Column(db.String(14))  # 일련번호
    trade_price = db.Column(db.String(10))  # 거래금액
    name = db.Column(db.String(128))  # 아파트명
    year = db.Column(db.String(4))  # 거래년도
    month = db.Column(db.String(2))  # 거래월
    day = db.Column(db.String(2))  # 거래일
    road_name = db.Column(db.String(32))  # 도로명
    si_gun_code = db.Column(db.String(5))  # 법정동시군구코드
    dong_code = db.Column(db.String(5))  # 법정동읍면동코드
    ep_area = db.Column(db.String(20))  # 전용면적
    floor = db.Column(db.Integer)  # 층수
    updated_at = db.Column(db.DateTime, server_default=db.func.now())
    code_info = db.Column(
        db.String(10), db.ForeignKey("address_codes.code"), nullable=False
    )

    def __repr__(self):
        return "serial_no = %s, trade_price = %s, ep_area =%s, updated_at = %s" % (
            self.serial_no,
            self.trade_price,
            self.ep_area,
            self.updated_at,
        )

    @property
    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "serial_no": self.serial_no,
            "trade_price": self.trade_price,
            "date": self.year + "-" + self.month + "-" + self.day,
            "road_name": self.road_name,
            "ep_area": self.ep_area,
            "floor": self.floor,
        }


with app.app_context():
    db.create_all()

# 최초 1회만 실행
connection = psycopg2.connect(
    host="dpg-cpfmi9n109ks73bne8rg-a",
    dbname="apartment_db_kx9l",
    user="apartment_db_kx9l_user",
    password="OE3vQp19JOsVSQsUHz5TNRvbQbgJaIvT",
    port="5432",
)

cur = connection.cursor()
cur.execute('SET statement_timeout VALUES "10min"')
# file = open("./resource/주소데이터_업데이트쿼리.sql", encoding="utf-8")
# for i in file:
#     cur.execute(i)


connection.commit()
connection.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/update.html")
def create():
    return render_template("update.html")


@app.route("/search/address/<address>")
def get_address(address):
    res = {}
    keyword = "%{}%".format(address)
    addr = AddressInfo.query.filter(AddressInfo.address_name.like(keyword)).all()

    res["codes"] = [t.serialize for t in addr]
    res["trade"] = []

    return jsonify(res)


@app.route("/trade/create", methods=["POST"])
def post():

    data = request.get_json()

    name = data[0]["value"]
    address = data[1]["value"]
    road_name = data[2]["value"]
    ep_area = data[3]["value"]
    floor = data[4]["value"]
    serial_no = data[5]["value"]
    trade_price = data[6]["value"]
    year = data[7]["value"]
    month = data[8]["value"]
    day = data[9]["value"]

    if address:
        res = {}
        addr = AddressInfo.query.filter(AddressInfo.address_name.like(address)).all()
        res["codes"] = [t.serialize for t in addr]
        # print(res)
        # print(res["codes"][0]["code"])
        codeinfo = res["codes"][0]["code"]

    if (
        name
        and road_name
        and ep_area
        and floor
        and trade_price
        and year
        and month
        and day
        and codeinfo
        and serial_no
    ):
        trade = TradeInfo()
        trade.name = name
        trade.road_name = road_name
        trade.ep_area = ep_area
        trade.floor = floor
        trade.trade_price = trade_price
        trade.year = year
        trade.month = month
        trade.day = day
        trade.serial_no = serial_no
        trade.code_info = codeinfo

        db.session.add(trade)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            return jsonify({"errors": "commit 실패"})
        return jsonify({})
    return jsonify({"errors": "Wrong Data"})


@app.route("/trade")
def get_trades():
    # 법정동코드별 실거래 가격 조회
    if request.method == "GET":

        year = request.args.get("year", None)
        month = request.args.get("month", None)
        address_cd = request.args.get("address_code", None)
        amount = request.args.get("amount", 10)
        page = request.args.get("page", 1)

        if year and month and address_cd:
            if amount != "all":
                res = (
                    TradeInfo.query.filter(
                        TradeInfo.year == year,
                        TradeInfo.month == month.rjust(2, "0"),
                        TradeInfo.code_info == address_cd,
                    )
                    .order_by(TradeInfo.day.desc())
                    .paginate(page=int(page), error_out=False, max_per_page=int(amount))
                )

                return jsonify(
                    {
                        "has_next": res.has_next,
                        "has_prev": res.has_prev,
                        "next_num": res.next_num,
                        "prev_num": res.prev_num,
                        "items": [t.serialize for t in res.items],
                    }
                )
            else:
                res = (
                    TradeInfo.query.filter(
                        TradeInfo.year == year,
                        TradeInfo.month == month.rjust(2, "0"),
                        TradeInfo.code_info == address_cd,
                    )
                    .order_by(TradeInfo.day.desc())
                    .all()
                )

                return jsonify(
                    {
                        "has_next": None,
                        "has_prev": None,
                        "next_num": None,
                        "prev_num": None,
                        "items": [t.serialize for t in res],
                    }
                )

    return jsonify({})


@app.route("/trade/update")
def update_trade_info():

    # 특정 년/월에 거래된 전체 실거래 내역 업데이트 (1회
    year = request.args.get("year", None)
    month = request.args.get("month", None)
    if year and month:

        codes = (
            db.session.query(AddressInfo.parent_code)
            .group_by(AddressInfo.parent_code)
            .all()
        )

        parent_codes = [code.parent_code for code in codes]

        request_url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"

        for pc in parent_codes:
            # print(pc)
            params = {
                "ServiceKey": config.Config.DATA_SECRET_KEY,
                "LAWD_CD": pc,
                "pageNo": 1,
                "numOfRows": 9999,
                "DEAL_YMD": year + month.strip().rjust(2, "0"),
            }

            res = requests.get(request_url, params=params)
            # print(res.text)

            root = ET.fromstring(res.text)

            for item in root.iter("item"):
                try:
                    trade = TradeInfo()
                    trade.name = (
                        ""
                        if item.find("아파트") is None
                        else item.find("아파트").text.strip()
                    )
                    trade.serial_no = (
                        ""
                        if item.find("일련번호") is None
                        else item.find("일련번호").text.strip()
                    )
                    trade.trade_price = item.find("거래금액").text.strip()
                    trade.year = item.find("년").text.strip()
                    trade.month = item.find("월").text.strip().rjust(2, "0")
                    trade.day = item.find("일").text.strip().rjust(2, "0")
                    trade.road_name = (
                        ""
                        if item.find("도로명") is None
                        else item.find("도로명").text.strip()
                    )
                    trade.si_gun_code = item.find("법정동시군구코드").text.strip()
                    trade.dong_code = item.find("법정동읍면동코드").text.strip()
                    trade.ep_area = (
                        ""
                        if item.find("전용면적") is None
                        else item.find("전용면적").text.strip()
                    )
                    trade.floor = (
                        "" if item.find("층") is None else item.find("층").text.strip()
                    )
                    trade.code_info = trade.si_gun_code + trade.dong_code
                except Exception as e:
                    print(e)
                    continue

                db.session.add(trade)
            try:
                db.session.commit()
            except:
                db.session.rollback()
                return jsonify({"errors": "commit 실패"})

        return jsonify(parent_codes)
    return jsonify({"errors": "parameter required (year, month)"})


# _list = ["1", "11", "111", "1111", "11111", "111111"]

# pool = ProcessPoolExecutor(max_workers=4)
# pool.map(update_trade_info, _list)


# if __name__ == "__main__":
#     pool = ProcessPoolExecutor(max_workers=4)
#     pool.map(update_trade_info, _list)
