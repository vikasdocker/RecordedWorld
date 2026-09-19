import unreal

at = unreal.AssetToolsHelpers.get_asset_tools()

mat = at.create_asset('M_VertexColor', '/Game/Materials', unreal.Material, None)
if not mat:
    unreal.log_error('Failed to create material asset')
    raise Exception('Failed to create material')

vc = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionVertexColor, -400, 0)
if not vc:
    unreal.log_error('Failed to create VertexColor expression')
    raise Exception('Failed to create VertexColor expression')

result = unreal.MaterialEditingLibrary.connect_material_property(vc, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
unreal.log('connect_material_property result: {}'.format(result))

unreal.EditorAssetLibrary.save_asset('/Game/Materials/M_VertexColor')
unreal.log('M_VertexColor created successfully with VertexColor -> BaseColor connection')
