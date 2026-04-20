import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# ==========================================
# 1. 页面配置与 UI 样式 (NIQING STUDIO 风格)
# ==========================================
st.set_page_config(page_title="NIQING | 股票策略终端", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stMetricValue"] { color: #d4af37 !important; }
    .stButton>button { border: 1px solid #d4af37; color: #d4af37; background: transparent; width: 100%; }
    .stButton>button:hover { background-color: #d4af37; color: black; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 访问授权逻辑
# ==========================================
def check_auth():
    if "auth" not in st.session_state:
        st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
        pwd = st.text_input("请输入访问令牌", type="password")
        if pwd == "niqing888": # 你的专属密码
            st.session_state.auth = True
            st.rerun()
        elif pwd:
            st.error("令牌无效")
        return False
    return True

if not check_auth():
    st.stop()

# ==========================================
# 3. 核心功能引擎 (增强版)
# ==========================================
class StockEngine:
    @staticmethod
    def retry_call(func, *args, **kwargs):
        """通用重试逻辑，应对云端网络波动"""
        for i in range(3): # 最多尝试3次
            try:
                data = func(*args, **kwargs)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                if i == 2: st.warning(f"接口调用异常: {e}")
                time.sleep(1) # 等待1秒后重试
        return pd.DataFrame()

    @classmethod
    @st.cache_data(ttl=600)
    def get_realtime(cls, threshold):
        """实时扫描全A股"""
        df = cls.retry_call(ak.stock_zh_a_spot_em)
        if df.empty: return df
        
        # 转换并清洗数据
        cols = ['今开', '最新价', '最高', '最低', '成交额']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        df = df.dropna(subset=cols)
        
        # 阴线十字星逻辑
        df['entity'] = (df['今开'] - df['最新价']).abs()
        df['range'] = df['最高'] - df['最低']
        
        mask = (df['最新价'] < df['今开']) & \
               (df['range'] > 0) & \
               (df['entity'] / df['range'] <= threshold) & \
               (df['成交额'] > 20000000)
        
        res = df[mask].copy()
        res['形态评分'] = (1 - res['entity'] / res['range']) * 100
        return res[['代码', '名称', '最新价', '涨跌幅', '形态评分', '成交额']]

    @classmethod
    def get_hist_backtest(cls, symbol, days, threshold):
        """单股回测"""
        # 注意：这里限制了日期，能显著提高加载速度
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days+20)).strftime('%Y%m%d')
        df = cls.retry_call(ak.stock_zh_a_hist, symbol=symbol, period="daily", start_date=start_date, adjust="qfq")
        
        if df.empty: return df
        
        df['entity'] = (df['开盘'] - df['收盘']).abs()
        df['range'] = df['最高'] - df['最低']
        df['signal'] = (df['收盘'] < df['开盘']) & (df['range'] > 0) & (df['entity'] / df['range'] <= threshold)
        
        for d in [1, 3, 5]:
            df[f'yield_{d}d'] = (df['收盘'].shift(-d) / df['收盘'] - 1) * 100
        return df

# ==========================================
# 4. 界面布局
# ==========================================
st.title("妮情 · A股旗舰选股终端")
st.sidebar.header("终端配置")
sens = st.sidebar.slider("十字星灵敏度", 0.05, 0.25, 0.15)

t1, t2 = st.tabs(["🚀 实时全速扫描", "📈 策略胜率回测"])

with t1:
    if st.button("📡 启动全 A 股云端扫描"):
        with st.spinner("正在穿越防火墙获取数据..."):
            data = StockEngine.get_realtime(sens)
            if not data.empty:
                st.success(f"捕获成功！今日信号点：{len(data)}")
                st.dataframe(data.sort_values('形态评分', ascending=False), use_container_width=True)
            else:
                st.info("当前网络状况较差或无匹配信号，请重试。")

with t2:
    c1, c2 = st.columns([1, 3])
    with c1:
        code = st.text_input("代码", "600519")
        back_days = st.number_input("回测周期(天)", 120)
    
    if code:
        with st.spinner("正在计算历史胜率..."):
            h_data = StockEngine.get_hist_backtest(code, back_days, sens)
            if not h_data.empty:
                sigs = h_data[h_data['signal']]
                
                # 胜率展示
                m_cols = st.columns(3)
                for i, d in enumerate([1, 3, 5]):
                    v = sigs[f'yield_{d}d'].dropna()
                    if not v.empty:
                        m_cols[i].metric(f"{d}日胜率", f"{(v>0).sum()/len(v)*100:.1f}%", f"{v.mean():.2f}% 收益")
                
                # 图表
                fig = go.Figure(data=[go.Candlestick(x=h_data['日期'], open=h_data['开盘'], high=h_data['最高'], low=h_data['最低'], close=h_data['收盘'], name="K线")])
                fig.add_trace(go.Scatter(x=sigs['日期'], y=sigs['最高']*1.02, mode='markers', marker=dict(symbol='star', color='#d4af37', size=10), name="信号"))
                fig.update_layout(template="plotly_dark", height=500, margin=dict(t=0,b=0,l=0,r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("数据抓取超时，请稍后再试。")
