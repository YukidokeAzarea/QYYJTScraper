"""
数据库到Excel转换工具
将SQLite数据库中的债券文档数据导出为Excel文件
支持多种导出格式和筛选选项
"""

import sqlite3
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union
import argparse
import sys

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent))

from config import DATABASE_PATH, DATA_DIR
from database import DatabaseManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('db_to_excel.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class DatabaseToExcelConverter:
    """数据库到Excel转换器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化转换器
        
        Args:
            db_path: 数据库文件路径，默认为配置文件中的路径
        """
        self.db_path = db_path or str(DATABASE_PATH)
        self.db_manager = DatabaseManager(self.db_path)
        
    def get_all_data(self) -> pd.DataFrame:
        """
        获取所有数据
        
        Returns:
            pd.DataFrame: 包含所有债券文档数据的DataFrame
        """
        try:
            with self.db_manager:
                documents = self.db_manager.get_all_documents()
                
            if not documents:
                logger.warning("数据库中没有数据")
                return pd.DataFrame()
            
            # 转换为DataFrame
            df = pd.DataFrame(documents)
            
            # 数据清理和格式化
            df = self._clean_data(df)
            
            logger.info(f"成功获取 {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return pd.DataFrame()
    
    def get_data_by_bond(self, bond_name: str) -> pd.DataFrame:
        """
        根据债券名称获取数据
        
        Args:
            bond_name: 债券名称
            
        Returns:
            pd.DataFrame: 指定债券的文档数据
        """
        try:
            with self.db_manager:
                documents = self.db_manager.get_documents_by_bond(bond_name)
                
            if not documents:
                logger.warning(f"未找到债券 '{bond_name}' 的数据")
                return pd.DataFrame()
            
            df = pd.DataFrame(documents)
            df = self._clean_data(df)
            
            logger.info(f"成功获取债券 '{bond_name}' 的 {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"获取债券数据失败: {e}")
            return pd.DataFrame()
    
    def get_data_by_type(self, document_type: str) -> pd.DataFrame:
        """
        根据文档类型获取数据
        
        Args:
            document_type: 文档类型
            
        Returns:
            pd.DataFrame: 指定类型的文档数据
        """
        try:
            with self.db_manager:
                documents = self.db_manager.get_documents_by_type(document_type)
                
            if not documents:
                logger.warning(f"未找到类型 '{document_type}' 的数据")
                return pd.DataFrame()
            
            df = pd.DataFrame(documents)
            df = self._clean_data(df)
            
            logger.info(f"成功获取类型 '{document_type}' 的 {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"获取类型数据失败: {e}")
            return pd.DataFrame()
    
    def get_data_by_date_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        根据日期范围获取数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: 指定日期范围的文档数据
        """
        try:
            with self.db_manager:
                documents = self.db_manager.get_documents_by_date_range(start_date, end_date)
                
            if not documents:
                logger.warning(f"未找到日期范围 '{start_date}' 到 '{end_date}' 的数据")
                return pd.DataFrame()
            
            df = pd.DataFrame(documents)
            df = self._clean_data(df)
            
            logger.info(f"成功获取日期范围的 {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"获取日期范围数据失败: {e}")
            return pd.DataFrame()
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清理和格式化数据
        
        Args:
            df: 原始DataFrame
            
        Returns:
            pd.DataFrame: 清理后的DataFrame
        """
        if df.empty:
            return df
        
        # 重命名列名为中文
        column_mapping = {
            'id': 'ID',
            'bond_short_name': '债券简称',
            'document_title': '文档标题',
            'document_type': '文档类型',
            'download_url': '下载链接',
            'file_size': '文件大小',
            'publication_date': '发布日期',
            'scraped_at': '抓取时间'
        }
        
        df = df.rename(columns=column_mapping)
        
        # 格式化日期
        if '发布日期' in df.columns:
            df['发布日期'] = pd.to_datetime(df['发布日期'], errors='coerce')
        
        if '抓取时间' in df.columns:
            df['抓取时间'] = pd.to_datetime(df['抓取时间'], errors='coerce')
        
        # 处理空值
        df = df.fillna('')
        
        return df
    
    def export_to_excel(self, 
                       df: pd.DataFrame, 
                       output_path: str,
                       sheet_name: str = "债券文档数据",
                       include_index: bool = False) -> bool:
        """
        导出DataFrame到Excel文件
        
        Args:
            df: 要导出的DataFrame
            output_path: 输出文件路径
            sheet_name: 工作表名称
            include_index: 是否包含索引
            
        Returns:
            bool: 导出是否成功
        """
        try:
            if df.empty:
                logger.warning("没有数据可导出")
                return False
            
            # 确保输出目录存在
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 导出到Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=include_index)
                
                # 获取工作表对象以进行格式化
                worksheet = writer.sheets[sheet_name]
                
                # 自动调整列宽
                self._auto_adjust_column_width(worksheet, df)
            
            logger.info(f"成功导出到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return False
    
    def _auto_adjust_column_width(self, worksheet, df: pd.DataFrame):
        """
        自动调整Excel列宽
        
        Args:
            worksheet: Excel工作表对象
            df: DataFrame对象
        """
        try:
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # 设置列宽，最小10，最大50
                adjusted_width = min(max(max_length + 2, 10), 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
                
        except Exception as e:
            logger.warning(f"自动调整列宽失败: {e}")
    
    def export_summary_report(self, output_path: str) -> bool:
        """
        导出汇总报告
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 导出是否成功
        """
        try:
            with self.db_manager:
                stats = self.db_manager.get_statistics()
            
            if not stats:
                logger.warning("无法获取统计信息")
                return False
            
            # 创建汇总数据
            summary_data = []
            
            # 总体统计
            summary_data.append({
                '统计项目': '总文档数',
                '数值': stats.get('total_documents', 0),
                '说明': '数据库中所有文档的总数'
            })
            
            summary_data.append({
                '统计项目': '总债券数',
                '数值': stats.get('total_bonds', 0),
                '说明': '数据库中涉及的债券总数'
            })
            
            summary_data.append({
                '统计项目': '日期范围',
                '数值': f"{stats.get('date_range', {}).get('start', 'N/A')} 至 {stats.get('date_range', {}).get('end', 'N/A')}",
                '说明': '文档发布的时间范围'
            })
            
            # 文档类型统计
            doc_types = stats.get('document_types', {})
            for doc_type, count in doc_types.items():
                summary_data.append({
                    '统计项目': f'文档类型: {doc_type}',
                    '数值': count,
                    '说明': f'{doc_type}类型的文档数量'
                })
            
            # 债券统计（前10个）
            bond_stats = stats.get('bond_statistics', [])
            for i, bond_stat in enumerate(bond_stats[:10]):
                summary_data.append({
                    '统计项目': f'债券文档数排名 {i+1}',
                    '数值': bond_stat.get('count', 0),
                    '说明': f"债券: {bond_stat.get('bond_short_name', 'N/A')}"
                })
            
            # 创建DataFrame
            summary_df = pd.DataFrame(summary_data)
            
            # 导出到Excel
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                summary_df.to_excel(writer, sheet_name="汇总报告", index=False)
                
                # 格式化汇总报告
                worksheet = writer.sheets["汇总报告"]
                self._auto_adjust_column_width(worksheet, summary_df)
            
            logger.info(f"成功导出汇总报告到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出汇总报告失败: {e}")
            return False
    
    def export_multiple_sheets(self, output_path: str) -> bool:
        """
        导出多工作表Excel文件
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 导出是否成功
        """
        try:
            # 获取所有数据
            all_data = self.get_all_data()
            if all_data.empty:
                logger.warning("没有数据可导出")
                return False
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 1. 全部数据
                all_data.to_excel(writer, sheet_name="全部数据", index=False)
                
                # 2. 按债券分组
                bond_groups = all_data.groupby('债券简称')
                for bond_name, group_df in bond_groups:
                    # 限制工作表名称长度
                    sheet_name = bond_name[:30] if len(bond_name) > 30 else bond_name
                    group_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 3. 按文档类型分组
                type_groups = all_data.groupby('文档类型')
                for doc_type, group_df in type_groups:
                    sheet_name = f"类型_{doc_type}"[:30]
                    group_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 4. 汇总统计
                self._create_summary_sheet(writer, all_data)
            
            logger.info(f"成功导出多工作表Excel到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出多工作表Excel失败: {e}")
            return False
    
    def _create_summary_sheet(self, writer, df: pd.DataFrame):
        """
        创建汇总统计工作表
        
        Args:
            writer: Excel写入器
            df: 数据DataFrame
        """
        try:
            # 按债券统计
            bond_summary = df.groupby('债券简称').agg({
                'ID': 'count',
                '文档类型': lambda x: ', '.join(x.unique()),
                '发布日期': ['min', 'max']
            }).round(2)
            
            bond_summary.columns = ['文档数量', '文档类型', '最早发布日期', '最新发布日期']
            bond_summary = bond_summary.reset_index()
            
            # 按文档类型统计
            type_summary = df.groupby('文档类型').agg({
                'ID': 'count',
                '债券简称': 'nunique'
            }).round(2)
            
            type_summary.columns = ['文档数量', '涉及债券数']
            type_summary = type_summary.reset_index()
            
            # 写入汇总数据
            bond_summary.to_excel(writer, sheet_name="债券汇总", index=False)
            type_summary.to_excel(writer, sheet_name="类型汇总", index=False)
            
        except Exception as e:
            logger.warning(f"创建汇总工作表失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据库到Excel转换工具')
    parser.add_argument('--output', '-o', default='data/exported_data.xlsx', 
                       help='输出Excel文件路径')
    parser.add_argument('--bond', '-b', help='指定债券名称')
    parser.add_argument('--type', '-t', help='指定文档类型')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--summary', action='store_true', help='导出汇总报告')
    parser.add_argument('--multi-sheet', action='store_true', help='导出多工作表Excel')
    parser.add_argument('--db-path', help='数据库文件路径')
    
    args = parser.parse_args()
    
    # 创建转换器
    converter = DatabaseToExcelConverter(args.db_path)
    
    # 检查数据库是否存在
    if not Path(converter.db_path).exists():
        logger.error(f"数据库文件不存在: {converter.db_path}")
        return
    
    try:
        if args.summary:
            # 导出汇总报告
            output_path = args.output.replace('.xlsx', '_summary.xlsx')
            success = converter.export_summary_report(output_path)
            
        elif args.multi_sheet:
            # 导出多工作表Excel
            output_path = args.output.replace('.xlsx', '_multi_sheet.xlsx')
            success = converter.export_multiple_sheets(output_path)
            
        else:
            # 根据条件获取数据
            if args.bond:
                df = converter.get_data_by_bond(args.bond)
                output_path = args.output.replace('.xlsx', f'_bond_{args.bond}.xlsx')
            elif args.type:
                df = converter.get_data_by_type(args.type)
                output_path = args.output.replace('.xlsx', f'_type_{args.type}.xlsx')
            elif args.start_date and args.end_date:
                df = converter.get_data_by_date_range(args.start_date, args.end_date)
                output_path = args.output.replace('.xlsx', f'_date_{args.start_date}_to_{args.end_date}.xlsx')
            else:
                df = converter.get_all_data()
                output_path = args.output
            
            # 导出数据
            success = converter.export_to_excel(df, output_path)
        
        if success:
            print(f"✅ 导出成功: {output_path}")
        else:
            print("❌ 导出失败")
            
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        print(f"❌ 程序执行失败: {e}")


if __name__ == "__main__":
    main()
