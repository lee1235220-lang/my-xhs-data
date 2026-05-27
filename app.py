"""
小红书矩阵内容赛马与数据洞察大屏 — Streamlit 前端（防空熔断版 v7.0）
============================================================
【核心修复】：引入 len() 与 st.stop() 双重物理熔断，彻底杜绝空表调用引发的异常
"""

import streamlit as st
import pandas as pd
from supabase import create_client

# ============================================================
#   Supabase 云端凭证
# ============================================================
SUPABASE_URL = "https://dtpqcmuchzpysozfftrs.supabase.co"
SUPABASE_KEY = "sb_publishable_DtvjWjosXH_xFl7bZAiygQ_XzL8znua"
TABLE_NAME   = "xhs_data"

# ============================================================
#   防断流纯净数据加载层
# ============================================================

def load_notes() -> pd.DataFrame:
    """直连云端数据库，执行高强度清洗与骨架强制对齐"""
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        resp = supabase.table(TABLE_NAME).select("*").execute()
        
        # 边界防御：数据源为空直接切断
        if not resp.data or len(resp.data) == 0:
            return pd.DataFrame()
        
        df = pd.DataFrame(resp.data)
        
        # 1. 字段格式标准化
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # 2. 核心别名动态对齐
        if "collections" in df.columns and "collects" not in df.columns:
            df["collects"] = df["collections"]
        if "link" in df.columns and "url" not in df.columns:
            df["url"] = df["link"]
            
        # 3. 强制构建标准数据骨架（彻底移除 theme 字段）
        required_columns = {
            "note_id": "",
            "account_name": "未知账号",
            "title": "无标题",
            "likes": 0,
            "comments": 0,
            "collects": 0,
            "publish_date": "未知",
            "url": ""
        }
        
        for col, default_val in required_columns.items():
            if col not in df.columns:
                df[col] = default_val
            else:
                if col in ["likes", "comments", "collects"]:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                else:
                    df[col] = df[col].fillna(default_val).astype(str)
                    
        return df
    except Exception as e:
        st.error(f"❌ 从云端读取数据时发生异常: {e}")
        return pd.DataFrame()


# ============================================================
#   Streamlit 视图渲染层
# ============================================================

st.set_page_config(page_title="小红书全矩阵数据大屏", layout="wide")

st.title("📊 小红书全矩阵赛马与数据洞察大屏")
st.markdown("云端网关数据自动同步，适配全口径矩阵运营模型。")
st.markdown("---")

# 加载清洗后的数据
df_notes = load_notes()

# 🚨 【核心杀招】：全自动强熔断机制
# 只要行数为 0，直接在此处封死程序，后续所有图表和表格代码连执行的机会都没有
if df_notes.empty or len(df_notes) == 0:
    st.info("💡 目前云端数据库中未检测到有效笔记数据。请确保本地 `excel_watcher.py` 正在运行，并至少将一张有效的全量 Excel 报表拖入 `data_input` 文件夹中进行同步。")
    st.stop()

# ============================================================
#   若通过熔断，执行标准业务渲染
# ============================================================

# 1. 顶部核心指标看板
total_accounts = df_notes["account_name"].nunique()
total_notes = len(df_notes)
total_likes = df_notes["likes"].sum()

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("👁️ 监控账号矩阵规模", f"{total_accounts} 个")
with c2:
    st.metric("📄 矩阵累计发布笔记", f"{total_notes} 篇")
with c3:
    st.metric("🔥 矩阵斩获总点赞量", f"{total_likes} 次")

st.markdown("---")

# 2. 全矩阵赛马竞争走势图
st.subheader("🏁 全矩阵账号竞争对比图 (大盘总览)")
df_g = df_notes.groupby("account_name").agg({
    "likes": "sum",
    "collects": "sum"
}).reset_index()

if not df_g.empty and len(df_g) > 0:
    df_g = df_g.rename(columns={
        "account_name": "账号名称",
        "likes": "总点赞量",
        "collects": "总收藏量"
    })
    df_bar = df_g.set_index("账号名称")[["总点赞量", "总收藏量"]]
    st.bar_chart(df_bar, use_container_width=True)
else:
    st.warning("暂无满足图表渲染条件的数据。")

st.markdown("---")

# 3. 原始明细透视表
st.subheader("📋 矩阵全量笔记原始数据表")
df_view = df_notes.sort_values(by=["publish_date", "likes"], ascending=False).copy()

df_view = df_view.rename(columns={
    "account_name": "账号",
    "title":        "标题",
    "likes":        "点赞数",
    "comments":     "评论数",
    "collects":     "收藏数",
    "publish_date": "发布日期",
    "url":          "链接"
})

column_order = ["账号", "标题", "发布日期", "点赞数", "评论数", "收藏数", "链接"]
df_view = df_view[[c for c in column_order if c in df_view.columns]]

# 再次进行行数安全校验
if not df_view.empty and len(df_view) > 0:
    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("⚠️ 暂无明细数据支撑。")