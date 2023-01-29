import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, JsCode
from st_aggrid.shared import GridUpdateMode
import warnings
from pandas.api.types import (
	is_categorical_dtype,
	is_datetime64_any_dtype,
	is_numeric_dtype,
	is_object_dtype,
)

def aggrid_multi_select(df: pd.DataFrame, website = None, list_of_text = None):
	"""
	Creates an st-aggrid interactive table based on a dataframe.
	Return a dataframe with the selected rows.
	----
	Parameters:
	----------
	df: pd.DataFrame
		Dataframe to be displayed in the table
	website: str
		Website name
	list_of_text: list
		List of part numbers to highlight their corresponding rows a light green color.
		This is used for showing what parts have already been added to the database.
	
	Returns:
	--------
	df_sel_row: pd.DataFrame
		Dataframe with the rows selected by the user on interactive table.
	"""
	# gd.configure_pagination(enabled=True)
	gd = GridOptionsBuilder.from_dataframe(df)#, min_column_width=150)
	gd.configure_side_bar() #Add a sidebar
	gd.configure_default_column(
								groupable=True, 
								# value=True, 
								enableRowGroup=True,
								floatingFilter = True,
								filter = "agSetColumnFilter",
								# aggFunc="sum",
								# suppressSyncLayoutWithGrid=True,
								# contractColumnSelection=True, 
								# suppressColumnExpandAll = True,
								# filter=True
								)
	for column in df.columns:
		if is_numeric_dtype(df[column]):
			gd.configure_column(column, filter = "agNumberColumnFilter")
		else:
			gd.configure_column(column, filter = "agTextColumnFilter")


	gd.configure_selection(selection_mode="multiple", 
							use_checkbox=True, 
							groupSelectsChildren=True,
							groupSelectsFiltered=True,
							rowMultiSelectWithClick=True, 
							# suppressColumnExpandAll = True,
							)
	gridoptions = gd.build()
	# gridoptions['getRowStyle'] = jscode
	grid_table = AgGrid(
						df,
						# filtered_df.loc[:, cols_to_be_shown],
						height=600,
						gridOptions=gridoptions,
						# fit_columns_on_grid_load=True,
						update_mode=GridUpdateMode.SELECTION_CHANGED,
						columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
						enable_enterprise_modules=True,
						# allow_unsafe_jscode=True,
						# theme="material"
						)

	sel_row = grid_table["selected_rows"]
	# node_id = grid_table["selected_row_ids"]
	df_sel_row = pd.DataFrame(sel_row)
	return df_sel_row


def aggrid_single_select(df: pd.DataFrame, website = None):
	"""
	Creates an st-aggrid interactive table based on a dataframe.
	Return a dataframe with the selected rows
	"""
	with warnings.catch_warnings():
		warnings.simplefilter(action='ignore', category=FutureWarning)
		gd = GridOptionsBuilder.from_dataframe(df)#, min_column_width=150)
		gd.configure_pagination(enabled=True)
		gd.configure_side_bar() #Add a sidebar
		gd.configure_default_column(
									groupable=True, 
									# value=True, 
									enableRowGroup=True,
									floatingFilter = True,
									filter = "agSetColumnFilter",
									# aggFunc="sum",
									# suppressSyncLayoutWithGrid=True,
									# contractColumnSelection=True, 
									# suppressColumnExpandAll = True,
									# filter=True
									)
		for column in df.columns:
			if is_numeric_dtype(df[column]):
				gd.configure_column(column, filter = "agNumberColumnFilter")
			else:
				gd.configure_column(column, filter = "agTextColumnFilter")


		gd.configure_selection(selection_mode="single", 
								# use_checkbox=True, 
								groupSelectsChildren=True,
								groupSelectsFiltered=True,
								rowMultiSelectWithClick=True, 
								# suppressColumnExpandAll = True,
								)
		gridoptions = gd.build()
		grid_table = AgGrid(
							df,
							# filtered_df.loc[:, cols_to_be_shown],
							height=600,
							gridOptions=gridoptions,
							# fit_columns_on_grid_load=True,
							update_mode=GridUpdateMode.SELECTION_CHANGED,
							columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
							enable_enterprise_modules=True,
							# theme="material"
							)

		sel_row = grid_table["selected_rows"]
		# node_id = grid_table["selected_row_ids"]
		df_sel_row = pd.DataFrame(sel_row)
	return df_sel_row
