import streamlit as st
import akshare as ak
import pandas as pd
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="NIQING | 双窗口并行雷达", layout="wide")

# --- 2. 高可用抓取逻辑 (带缓存保护) ---
@st.cache_data(ttl=60)
def get_market_data():
    """尝试从东财抓取，挂了就切新浪"""
    try:
        df = ak.stock_zh_a_spot_em()
        return df, "东财源"
    except:
        try:
            df = ak.stock_zh_a_spot_sina()
            return df, "新浪源"
        except:
            return None, None

def get_hist_safe(symbol):
    try:
        time.sleep(0.3) # 强制冷却，防止双窗口同时请求导致封号
        return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(25)
    except:
        return None

# --- 3. 左侧控制中心 (控制两个窗口的开关) ---
with st.sidebar:
    st.title("妮情 · 并行控制台")
    st.divider()
    
    st.subheader("📡 任务选择")
    show_star = st.checkbox("开启：阴线十字星监控", value=True)
    show_gold = st.checkbox("开启：金叉趋势预警", value=True)
    
    st.divider()
    vol_threshold = st.number_input("全局准入额 (亿)", value=5.0)
    
    if st.button("🚀 执行双窗同步扫描"):
        st.cache_data.clear()
        st.rerun()

# --- 4. 右侧结果展示区 (双栏并行布局) ---
st.header("NIQING STUDIO · 双窗口同步监测")

# 创建左右两列
col_left, col_right = st.columns(2)

# --- 左窗口：阴线十字星 ---
with col_left:
    if show_star:
        st.subheader("🟢 阴线十字星监控")
        with st.status("正在扫描形态...", expanded=False):
            df, src = get_market_data()
            if df is not None:
                df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
                pool = df[df['成交额'] >= vol_threshold * 100000000].copy()
                res = []
                for _, row in pool.iterrows():
                    o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                    if c < o and (h-l) > 0: # 阴线判断
                        if (abs(o-c)/(h-l)) <= 0.12:
                            res.append({"代码":row['代码'], "名称":row['名称'], "涨跌":row['涨跌幅']})
                if res:
                    st.dataframe(pd.DataFrame(res), use_container_width=True)
                else:
                    st.info("暂无阴线信号")
            else:
                st.error("数据链路断开")
    else:
        st.info("左窗口已关闭")

# --- 右窗口：金叉预警 ---
with col_right:
    if show_gold:
        st.subheader("⚡ 金叉趋势预警")
        with st.status("正在计算均线...", expanded=False):
            df, src = get_market_data()
            if df is not None:
                df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
                # 为保稳定，右窗口只扫成交额前 20 的票
                pool = df[df['成交额'] >= vol_threshold * 100000000].sort_values('成交额', ascending=False).head(20)
                gold_res = []
                for _, row in pool.iterrows():
                    h_df = get_hist_safe(row['代码'])
                    if h_df is not None and len(h_df) >= 15:
                        # KDJ 逻辑
                        l9, h9 = h_df['最低'].rolling(9).min(), h_df['最高'].rolling(9).max()
                        rsv = (h_df['收盘'] - l9) / (h9 - l9) * 100
                        k = rsv.ewm(com=2).mean()
                        d = k.ewm(com=2).mean()
                        j = 3*k - 2*d
                        if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                            gold_res.append({"代码":row['代码'], "名称":row['名称'], "J值":round(j.iloc[-1],2)})
                if gold_res:
                    st.dataframe(pd.DataFrame(gold_res), use_container_width=True)
                else:
                    st.info("活跃池暂无金叉")
    else:
        st.info("右窗口已关闭")
