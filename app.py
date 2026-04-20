import streamlit as st
import akshare as ak
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 页面配置 ---
st.set_page_config(page_title="NIQING | 全指标策略终端", layout="wide")

# --- 核心引擎 ---
class AdvancedEngine:
    @staticmethod
    def get_with_retry(func, *args, **kwargs):
        for i in range(3):
            try:
                data = func(*args, **kwargs)
                if data is not None and not data.empty: return data
            except:
                time.sleep(1)
        return pd.DataFrame()

    @classmethod
    @st.cache_data(ttl=600)
    def scan_market_pro(cls, threshold):
        """实时扫描：集成成交量分析"""
        df = cls.get_with_retry(ak.stock_zh_a_spot_em)
        if df.empty: return df
        
        cols = ['今开', '最新价', '最高', '最低', '成交额', '成交量']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        df = df.dropna(subset=cols)
        
        # 计算量化指标
        df['entity'] = (df['今开'] - df['最新价']).abs()
        df['range'] = df['最高'] - df['最低']
        
        # 核心逻辑：阴线十字星 + 成交量过滤 (成交额 > 3000万)
        mask = (df['最新价'] < df['今开']) & (df['range'] > 0) & \
               (df['entity'] / df['range'] <= threshold) & (df['成交额'] > 30000000)
        
        res = df[mask].copy()
        # 计算相对于昨收的实体强度
        res['形态评分'] = (1 - res['entity'] / res['range']) * 100
        return res[['代码', '名称', '最新价', '涨跌幅', '形态评分', '成交量', '成交额']]

    @classmethod
    def get_full_indicators(cls, symbol, days):
        """获取全指标数据：KDJ + 成交量MA"""
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days+60)).strftime('%Y%m%d')
        df = cls.get_with_retry(ak.stock_zh_a_hist, symbol=symbol, period="daily", start_date=start_date, adjust="qfq")
        
        if df.empty: return df
        
        # 1. 计算 KDJ (9, 3, 3)
        kdj = ta.kdj(high=df['最高'], low=df['最低'], close=df['收盘'], length=9, signal=3, count=3)
        df = pd.concat([df, kdj], axis=1)
        
        # 2. 计算成交量均线
        df['v_ma5'] = df['成交量'].rolling(5).mean()
        df['v_ma10'] = df['成交量'].rolling(10).mean()
        
        # 3. 标记十字星信号
        df['entity'] = (df['开盘'] - df['收盘']).abs()
        df['range'] = df['最高'] - df['最低']
        df['signal'] = (df['收盘'] < df['开盘']) & (df['range'] > 0) & (df['entity'] / df['range'] <= 0.15)
        
        return df

# --- 界面展示 ---
st.title("妮情 · 全量数据策略终端 (KDJ+VOL)")

t1, t2 = st.tabs(["🚀 深度扫描", "📊 多维指标回测"])

with t1:
    sens = st.slider("十字星灵敏度", 0.05, 0.25, 0.15)
    if st.button("开始全量快照扫描"):
        data = AdvancedEngine.scan_market_pro(sens)
        st.dataframe(data.sort_values('形态评分', ascending=False), use_container_width=True)

with t2:
    col_a, col_b = st.columns([1, 4])
    with col_a:
        s_code = st.text_input("股票代码", "600519")
        s_days = st.number_input("周期", 100)
    
    if s_code:
        df_full = AdvancedEngine.get_full_indicators(s_code, s_days)
        if not df_full.empty:
            # 使用 Subplots 创建主图和副图
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3],
                                subplot_titles=("K线与信号", "成交量", "KDJ 指标"))
            
            # 1. K线图
            fig.add_trace(go.Candlestick(x=df_full['日期'], open=df_full['开盘'], high=df_full['最高'], low=df_full['最低'], close=df_full['收盘'], name="K线"), row=1, col=1)
            # 信号点
            sigs = df_full[df_full['signal']]
            fig.add_trace(go.Scatter(x=sigs['日期'], y=sigs['最高']*1.02, mode='markers', marker=dict(symbol='diamond', size=10, color='gold'), name="十字星"), row=1, col=1)
            
            # 2. 成交量
            v_colors = ['red' if c < o else 'green' for c, o in zip(df_full['收盘'], df_full['开盘'])]
            fig.add_trace(go.Bar(x=df_full['日期'], y=df_full['成交量'], marker_color=v_colors, name="成交量"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_full['日期'], y=df_full['v_ma5'], line=dict(color='orange', width=1), name="V-MA5"), row=2, col=1)
            
            # 3. KDJ
            fig.add_trace(go.Scatter(x=df_full['日期'], y=df_full['K_9_3_3'], line=dict(color='white', width=1), name="K"), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_full['日期'], y=df_full['D_9_3_3'], line=dict(color='yellow', width=1), name="D"), row=3, col=1)
            fig.add_trace(go.Scatter(x=df_full['日期'], y=df_full['J_9_3_3'], line=dict(color='purple', width=1), name="J"), row=3, col=1)
            # 超买超卖线
            fig.add_hline(y=20, line_dash="dot", row=3, col=1, line_color="gray")
            fig.add_hline(y=80, line_dash="dot", row=3, col=1, line_color="gray")
            
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
