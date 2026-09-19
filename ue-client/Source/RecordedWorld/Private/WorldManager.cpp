#include "WorldManager.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/PostProcessVolume.h"
#include "Components/LightComponent.h"
#include "Engine/ExponentialHeightFog.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Materials/Material.h"

AWorldManager::AWorldManager()
{
	PrimaryActorTick.bCanEverTick = false;

	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	TerrainMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("TerrainMesh"));
	TerrainMesh->SetupAttachment(RootComponent);
	TerrainMesh->bUseAsyncCooking = true;

	RoadMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RoadMesh"));
	RoadMesh->SetupAttachment(RootComponent);
	RoadMesh->bUseAsyncCooking = true;

	BuildingMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("BuildingMesh"));
	BuildingMesh->SetupAttachment(RootComponent);
	BuildingMesh->bUseAsyncCooking = true;

	TreeMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("TreeMesh"));
	TreeMesh->SetupAttachment(RootComponent);
	TreeMesh->bUseAsyncCooking = true;

	MountainMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("MountainMesh"));
	MountainMesh->SetupAttachment(RootComponent);
	MountainMesh->bUseAsyncCooking = true;

	WaterMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("WaterMesh"));
	WaterMesh->SetupAttachment(RootComponent);
	WaterMesh->bUseAsyncCooking = true;

	StreetFurnitureMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("StreetFurnitureMesh"));
	StreetFurnitureMesh->SetupAttachment(RootComponent);
	StreetFurnitureMesh->bUseAsyncCooking = true;
}

void AWorldManager::BeginPlay()
{
	Super::BeginPlay();

	UE_LOG(LogTemp, Log, TEXT("WorldManager: Generating world (terrain=%f segments=%d)"), TerrainSize, TerrainSegments);
	const double StartTime = FPlatformTime::Seconds();

	CreateVertexColorMaterial();

	GenerateTerrain();
	GenerateRoads();
	GenerateBuildings();
	GenerateTrees();
	GenerateMountains();
	GenerateWaterFeature();
	GenerateStreetFurniture();
	SetupLightingAndPostProcess();
	ApplyMaterialToAllMeshes();

	const double Elapsed = FPlatformTime::Seconds() - StartTime;
	UE_LOG(LogTemp, Log, TEXT("WorldManager: World generated in %.2f seconds"), Elapsed);
}

float AWorldManager::ComputeTerrainHeight(float X, float Z) const
{
	const float H1 = FMath::Sin(X * 0.008f) * FMath::Cos(Z * 0.008f) * 4.0f;
	const float H2 = FMath::Sin(X * 0.02f + 1.3f) * FMath::Cos(Z * 0.015f + 0.7f) * 2.0f;
	const float H3 = FMath::Sin(X * 0.05f + 2.1f) * FMath::Cos(Z * 0.04f + 1.9f) * 0.8f;
	const float H4 = FMath::Sin(X * 0.1f) * FMath::Cos(Z * 0.1f) * 0.3f;
	float Height = H1 + H2 + H3 + H4;

	const float HalfRoad = RoadWidth * 0.5f;
	const bool bInRoadX = FMath::Abs(X) < HalfRoad;
	const bool bInRoadZ = FMath::Abs(Z) < HalfRoad;
	if (bInRoadX || bInRoadZ)
	{
		Height *= 0.02f;
	}
	else
	{
		const float NearRoad = HalfRoad + SidewalkWidth;
		const bool bNearRoadX = FMath::Abs(X) < NearRoad;
		const bool bNearRoadZ = FMath::Abs(Z) < NearRoad;
		if (bNearRoadX || bNearRoadZ)
		{
			Height *= 0.15f;
		}
	}

	return Height;
}

float AWorldManager::GetTerrainHeight(float X, float Z) const
{
	return ComputeTerrainHeight(X, Z);
}

void AWorldManager::GenerateTerrain()
{
	const int32 Segments = TerrainSegments;
	const float Size = TerrainSize;
	const float HalfSize = Size * 0.5f;
	const float Step = Size / Segments;

	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UVs;
	TArray<FLinearColor> Colors;

	const int32 VertCount = (Segments + 1) * (Segments + 1);
	Vertices.Reserve(VertCount);
	Normals.Reserve(VertCount);
	UVs.Reserve(VertCount);
	Colors.Reserve(VertCount);

	for (int32 iy = 0; iy <= Segments; iy++)
	{
		for (int32 ix = 0; ix <= Segments; ix++)
		{
			const float X = ix * Step - HalfSize;
			const float Y = iy * Step - HalfSize;
			const float H = ComputeTerrainHeight(X, Y);

			Vertices.Add(FVector(X, Y, H));
			UVs.Add(FVector2D(static_cast<float>(ix) / Segments, static_cast<float>(iy) / Segments));

			FLinearColor TerrainColor;
			if (FMath::Abs(X) < RoadWidth * 0.5f + SidewalkWidth + 0.5f ||
				FMath::Abs(Y) < RoadWidth * 0.5f + SidewalkWidth + 0.5f)
			{
				TerrainColor = FLinearColor(0.58f, 0.55f, 0.48f);
			}
			else
			{
				const float NoiseVal = (FMath::Sin(X * 0.3f) * FMath::Cos(Y * 0.25f) * 0.5f + 0.5f);
				const float R = FMath::Clamp(0.22f + NoiseVal * 0.10f, 0.0f, 1.0f);
				const float G = FMath::Clamp(0.50f + NoiseVal * 0.15f, 0.0f, 1.0f);
				const float B = FMath::Clamp(0.16f + NoiseVal * 0.06f, 0.0f, 1.0f);
				TerrainColor = FLinearColor(R, G, B);
			}
			Colors.Add(TerrainColor);
		}
	}

	for (int32 iy = 0; iy < Segments; iy++)
	{
		for (int32 ix = 0; ix < Segments; ix++)
		{
			const int32 I0 = iy * (Segments + 1) + ix;
			const int32 I1 = I0 + 1;
			const int32 I2 = I0 + (Segments + 1);
			const int32 I3 = I2 + 1;

			Triangles.Add(I0);
			Triangles.Add(I2);
			Triangles.Add(I1);

			Triangles.Add(I1);
			Triangles.Add(I2);
			Triangles.Add(I3);
		}
	}

	Normals.SetNumZeroed(Vertices.Num());
	TArray<FProcMeshTangent> Tangents;
	Tangents.SetNumZeroed(Vertices.Num());

	TerrainMesh->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, true);

	UE_LOG(LogTemp, Log, TEXT("Terrain: %d vertices, %d triangles"), Vertices.Num(), Triangles.Num() / 3);
}

void AWorldManager::GenerateRoads()
{
	const float HalfRoad = RoadWidth * 0.5f;
	const float HalfLen = RoadLength * 0.5f;
	const float RoadY = 0.03f;
	const float CurbHeight = 0.12f;
	const float SidewalkHeight = 0.15f;

	const FLinearColor RoadColor(0.133f, 0.133f, 0.133f);
	const FLinearColor SidewalkColor(0.541f, 0.541f, 0.478f);
	const FLinearColor LaneColor(0.867f, 0.867f, 0.333f);
	const FLinearColor CurbColor(0.667f, 0.600f, 0.533f);
	const FLinearColor EdgeLineColor(0.941f, 0.941f, 0.941f);

	AddBoxMesh(RoadMesh, FVector(0, 0, RoadY), FVector(HalfLen, HalfRoad, 0.03f), RoadColor);
	AddBoxMesh(RoadMesh, FVector(0, 0, RoadY), FVector(HalfRoad, HalfLen, 0.03f), RoadColor);

	AddBoxMesh(RoadMesh, FVector(0, HalfRoad + SidewalkWidth * 0.5f, SidewalkHeight * 0.5f),
		FVector(HalfLen, SidewalkWidth * 0.5f, SidewalkHeight * 0.5f), SidewalkColor);
	AddBoxMesh(RoadMesh, FVector(0, -(HalfRoad + SidewalkWidth * 0.5f), SidewalkHeight * 0.5f),
		FVector(HalfLen, SidewalkWidth * 0.5f, SidewalkHeight * 0.5f), SidewalkColor);
	AddBoxMesh(RoadMesh, FVector(HalfRoad + SidewalkWidth * 0.5f, 0, SidewalkHeight * 0.5f),
		FVector(SidewalkWidth * 0.5f, HalfLen, SidewalkHeight * 0.5f), SidewalkColor);
	AddBoxMesh(RoadMesh, FVector(-(HalfRoad + SidewalkWidth * 0.5f), 0, SidewalkHeight * 0.5f),
		FVector(SidewalkWidth * 0.5f, HalfLen, SidewalkHeight * 0.5f), SidewalkColor);

	AddBoxMesh(RoadMesh, FVector(0, HalfRoad + 0.05f, CurbHeight * 0.5f),
		FVector(HalfLen, 0.1f, CurbHeight * 0.5f), CurbColor);
	AddBoxMesh(RoadMesh, FVector(0, -(HalfRoad + 0.05f), CurbHeight * 0.5f),
		FVector(HalfLen, 0.1f, CurbHeight * 0.5f), CurbColor);
	AddBoxMesh(RoadMesh, FVector(HalfRoad + 0.05f, 0, CurbHeight * 0.5f),
		FVector(0.1f, HalfLen, CurbHeight * 0.5f), CurbColor);
	AddBoxMesh(RoadMesh, FVector(-(HalfRoad + 0.05f), 0, CurbHeight * 0.5f),
		FVector(0.1f, HalfLen, CurbHeight * 0.5f), CurbColor);

	AddBoxMesh(RoadMesh, FVector(0, 0, RoadY + 0.04f), FVector(HalfLen, 0.12f, 0.02f), LaneColor);
	AddBoxMesh(RoadMesh, FVector(0, 0, RoadY + 0.04f), FVector(0.12f, HalfLen, 0.02f), LaneColor);

	AddBoxMesh(RoadMesh, FVector(0, HalfRoad - 0.3f, RoadY + 0.04f), FVector(HalfLen, 0.08f, 0.015f), EdgeLineColor);
	AddBoxMesh(RoadMesh, FVector(0, -(HalfRoad - 0.3f), RoadY + 0.04f), FVector(HalfLen, 0.08f, 0.015f), EdgeLineColor);
	AddBoxMesh(RoadMesh, FVector(HalfRoad - 0.3f, 0, RoadY + 0.04f), FVector(0.08f, HalfLen, 0.015f), EdgeLineColor);
	AddBoxMesh(RoadMesh, FVector(-(HalfRoad - 0.3f), 0, RoadY + 0.04f), FVector(0.08f, HalfLen, 0.015f), EdgeLineColor);

	UE_LOG(LogTemp, Log, TEXT("Roads: Cross-shaped road network generated"));
}

void AWorldManager::GenerateBuildings()
{
	const FLinearColor BuildingColors[] =
	{
		FLinearColor(0.95f, 0.65f, 0.70f),
		FLinearColor(0.60f, 0.85f, 0.85f),
		FLinearColor(0.95f, 0.90f, 0.75f),
		FLinearColor(0.80f, 0.75f, 0.85f),
		FLinearColor(0.70f, 0.85f, 0.70f),
		FLinearColor(0.95f, 0.80f, 0.60f),
		FLinearColor(0.85f, 0.85f, 0.90f),
		FLinearColor(0.90f, 0.70f, 0.75f),
	};
	const int32 NumColors = UE_ARRAY_COUNT(BuildingColors);

	const FLinearColor WindowColor(0.45f, 0.75f, 0.95f);
	const FLinearColor RoofColor(0.55f, 0.55f, 0.58f);
	const FLinearColor ACUnitColor(0.65f, 0.65f, 0.68f);

	int32 BuildingCount = 0;

	for (int32 bx = -BuildingGridExtent; bx <= BuildingGridExtent; bx++)
	{
		for (int32 bz = -BuildingGridExtent; bz <= BuildingGridExtent; bz++)
		{
			if (FMath::Abs(bx) <= 0 && FMath::Abs(bz) <= 0) continue;

			const float AbsX = FMath::Abs(static_cast<float>(bx) * BuildingGridSpacing);
			const float AbsZ = FMath::Abs(static_cast<float>(bz) * BuildingGridSpacing);
			if (AbsX < RoadWidth + SidewalkWidth + 2.0f || AbsZ < RoadWidth + SidewalkWidth + 2.0f) continue;

			const float JitterX = (FMath::FRand() - 0.5f) * 3.0f;
			const float JitterZ = (FMath::FRand() - 0.5f) * 3.0f;
			const float X = bx * BuildingGridSpacing + JitterX;
			const float Z = bz * BuildingGridSpacing + JitterZ;
			const float BaseY = ComputeTerrainHeight(X, Z);

			const float Width = 5.0f + FMath::FRand() * 4.0f;
			const float Depth = 5.0f + FMath::FRand() * 4.0f;
			const float Height = 6.0f + FMath::FRand() * 18.0f;
			const int32 ColorIdx = FMath::RandRange(0, NumColors - 1);
			const FLinearColor BaseColor = BuildingColors[ColorIdx];

			AddBoxMesh(BuildingMesh, FVector(X, Z, BaseY + Height * 0.5f),
				FVector(Width * 0.5f, Depth * 0.5f, Height * 0.5f), BaseColor);

			const int32 NumFloors = FMath::Max(1, FMath::FloorToInt(Height / 3.0f));
			const float FloorHeight = Height / NumFloors;
			for (int32 Floor = 0; Floor < NumFloors; Floor++)
			{
				const float WinY = BaseY + Floor * FloorHeight + FloorHeight * 0.5f;
				const int32 WindowsPerSide = FMath::Max(1, FMath::FloorToInt(Width / 2.0f));

				for (int32 w = 0; w < WindowsPerSide; w++)
				{
					const float Offset = (w - (WindowsPerSide - 1) * 0.5f) * 2.0f;
					AddBoxMesh(BuildingMesh, FVector(X + Offset, Z + Depth * 0.5f + 0.01f, WinY),
						FVector(0.7f, 0.05f, FloorHeight * 0.35f), WindowColor);
					AddBoxMesh(BuildingMesh, FVector(X + Offset, Z - Depth * 0.5f - 0.01f, WinY),
						FVector(0.7f, 0.05f, FloorHeight * 0.35f), WindowColor);
				}

				const int32 WindowsPerSideZ = FMath::Max(1, FMath::FloorToInt(Depth / 2.0f));
				for (int32 w = 0; w < WindowsPerSideZ; w++)
				{
					const float Offset = (w - (WindowsPerSideZ - 1) * 0.5f) * 2.0f;
					AddBoxMesh(BuildingMesh, FVector(X + Width * 0.5f + 0.01f, Z + Offset, WinY),
						FVector(0.05f, 0.7f, FloorHeight * 0.35f), WindowColor);
					AddBoxMesh(BuildingMesh, FVector(X - Width * 0.5f - 0.01f, Z + Offset, WinY),
						FVector(0.05f, 0.7f, FloorHeight * 0.35f), WindowColor);
				}
			}

			AddBoxMesh(BuildingMesh, FVector(X, Z, BaseY + Height + 0.15f),
				FVector(Width * 0.55f, Depth * 0.55f, 0.15f), RoofColor);

			if (FMath::FRand() > 0.4f)
			{
				const float ACX = X + (FMath::FRand() - 0.5f) * Width * 0.4f;
				const float ACZ = Z + (FMath::FRand() - 0.5f) * Depth * 0.4f;
				AddBoxMesh(BuildingMesh, FVector(ACX, ACZ, BaseY + Height + 0.45f),
					FVector(0.8f, 0.8f, 0.3f), ACUnitColor);
			}

			BuildingCount++;
		}
	}

	UE_LOG(LogTemp, Log, TEXT("Buildings: %d placed"), BuildingCount);
}

void AWorldManager::GenerateTrees()
{
	struct FClusterCenter
	{
		float X, Z;
	};

	const FClusterCenter Centers[] =
	{
		{80, 80}, {-100, 60}, {50, -120}, {-80, -90},
		{140, -40}, {-140, 120}, {30, 160}, {-60, -170},
		{170, 150}, {-180, -60}, {200, 80}, {-50, 200},
	};

	const FLinearColor TrunkColor(0.45f, 0.30f, 0.15f);
	const FLinearColor FoliageColors[] =
	{
		FLinearColor(0.15f, 0.55f, 0.12f),
		FLinearColor(0.20f, 0.60f, 0.16f),
		FLinearColor(0.25f, 0.65f, 0.20f),
	};

	int32 TreeCount = 0;

	for (const FClusterCenter& Center : Centers)
	{
		const int32 Count = TreeClusterCount + FMath::RandRange(0, 10);
		for (int32 i = 0; i < Count; i++)
		{
			const float Angle = FMath::FRand() * 2.0f * PI;
			const float Dist = FMath::FRand() * 30.0f;
			const float X = Center.X + FMath::Cos(Angle) * Dist;
			const float Z = Center.Z + FMath::Sin(Angle) * Dist;
			const float BaseY = ComputeTerrainHeight(X, Z);
			const float Scale = 0.6f + FMath::FRand() * 0.8f;

			const float TrunkH = 2.5f * Scale;
			const float TrunkR = 0.2f * Scale;
			const float FoliageH = 4.0f * Scale;
			const float FoliageR = 2.5f * Scale;

			const FLinearColor FoliageColor = FoliageColors[FMath::RandRange(0, 2)];

			AddCylinderMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH * 0.5f),
				TrunkR, TrunkH, TrunkColor, 8);
			AddConeMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH + FoliageH * 0.3f),
				FoliageR, FoliageH * 0.5f, FoliageColor, 10);
			AddConeMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH + FoliageH * 0.6f),
				FoliageR * 0.7f, FoliageH * 0.4f, FoliageColor, 10);
			AddConeMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH + FoliageH * 0.85f),
				FoliageR * 0.4f, FoliageH * 0.3f, FoliageColor, 10);

			TreeCount++;
		}
	}

	for (int32 i = 0; i < 30; i++)
	{
		const float X = (FMath::FRand() - 0.5f) * 400.0f;
		const float Z = (FMath::FRand() - 0.5f) * 400.0f;
		const float BaseY = ComputeTerrainHeight(X, Z);
		const float Scale = 0.5f + FMath::FRand() * 0.7f;

		const float TrunkH = 2.5f * Scale;
		const float TrunkR = 0.2f * Scale;
		const float FoliageH = 4.0f * Scale;
		const float FoliageR = 2.5f * Scale;

		const FLinearColor FoliageColor = FoliageColors[FMath::RandRange(0, 2)];

		AddCylinderMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH * 0.5f),
			TrunkR, TrunkH, TrunkColor, 8);
		AddConeMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH + FoliageH * 0.3f),
			FoliageR, FoliageH * 0.5f, FoliageColor, 10);
		AddConeMesh(TreeMesh, FVector(X, Z, BaseY + TrunkH + FoliageH * 0.6f),
			FoliageR * 0.7f, FoliageH * 0.4f, FoliageColor, 10);

		TreeCount++;
	}

	UE_LOG(LogTemp, Log, TEXT("Trees: %d placed"), TreeCount);
}

void AWorldManager::GenerateMountains()
{
	const FLinearColor SnowColor(0.941f, 0.941f, 0.980f);
	const FLinearColor RockColor(0.471f, 0.451f, 0.412f);
	const int32 RingSegments = 48;
	const int32 RingCount = 8;

	for (int32 Ring = 0; Ring < RingCount; Ring++)
	{
		const float Radius = MountainStartRadius + Ring * 20.0f;
		const float NextRadius = MountainStartRadius + (Ring + 1) * 20.0f;
		const float Height = MountainHeight * (1.0f + Ring * 0.15f);
		const float NextHeight = MountainHeight * (1.0f + (Ring + 1) * 0.15f);
		const FLinearColor Color = (Ring > RingCount * 0.6) ? SnowColor : RockColor;

		for (int32 Seg = 0; Seg < RingSegments; Seg++)
		{
			const float Angle1 = Seg * 2.0f * PI / RingSegments;
			const float Angle2 = (Seg + 1) * 2.0f * PI / RingSegments;

			const float X1 = FMath::Cos(Angle1) * Radius;
			const float Y1 = FMath::Sin(Angle1) * Radius;
			const float X2 = FMath::Cos(Angle2) * Radius;
			const float Y2 = FMath::Sin(Angle2) * Radius;
			const float X3 = FMath::Cos(Angle1) * NextRadius;
			const float Y3 = FMath::Sin(Angle1) * NextRadius;
			const float X4 = FMath::Cos(Angle2) * NextRadius;
			const float Y4 = FMath::Sin(Angle2) * NextRadius;

			const float H1 = ComputeTerrainHeight(X1, Y1);
			const float H3 = ComputeTerrainHeight(X3, Y3);

			TArray<FVector> Verts;
			Verts.Add(FVector(X1, Y1, H1));
			Verts.Add(FVector(X2, Y2, ComputeTerrainHeight(X2, Y2)));
			Verts.Add(FVector(X3, Y3, Height + H3));
			Verts.Add(FVector(X4, Y4, NextHeight + ComputeTerrainHeight(X4, Y4)));

			TArray<int32> Tris;
			Tris.Add(0); Tris.Add(2); Tris.Add(1);
			Tris.Add(1); Tris.Add(2); Tris.Add(3);

			TArray<FVector> Nrms;
			Nrms.Add(FVector::ZAxisVector);
			Nrms.Add(FVector::ZAxisVector);
			Nrms.Add(FVector::ZAxisVector);
			Nrms.Add(FVector::ZAxisVector);

			TArray<FVector2D> UV;
			UV.Add(FVector2D(0, 0));
			UV.Add(FVector2D(1, 0));
			UV.Add(FVector2D(0, 1));
			UV.Add(FVector2D(1, 1));

			TArray<FLinearColor> Clrs;
			Clrs.Add(Color); Clrs.Add(Color); Clrs.Add(Color); Clrs.Add(Color);

			MountainMesh->CreateMeshSection_LinearColor(MountainMesh->GetNumSections(),
				Verts, Tris, Nrms, UV, Clrs, TArray<FProcMeshTangent>(), false);
		}
	}

	UE_LOG(LogTemp, Log, TEXT("Mountains: %d rings generated"), RingCount);
}

void AWorldManager::GenerateWaterFeature()
{
	const FLinearColor WaterColor(0.118f, 0.314f, 0.588f);
	const float HalfWater = WaterSize * 0.5f;

	AddBoxMesh(WaterMesh, FVector(0, 0, WaterLevel),
		FVector(HalfWater, HalfWater, 0.1f), WaterColor);

	const FLinearColor RockCol(0.392f, 0.373f, 0.333f);
	const int32 RockCount = 16;
	for (int32 i = 0; i < RockCount; i++)
	{
		const float Angle = i * 2.0f * PI / RockCount;
		const float R = HalfWater + 1.5f;
		const float X = FMath::Cos(Angle) * R;
		const float Z = FMath::Sin(Angle) * R;
		const float BaseY = ComputeTerrainHeight(X, Z);

		AddBoxMesh(WaterMesh, FVector(X, Z, BaseY + 0.3f),
			FVector(0.6f, 0.5f, 0.3f), RockCol);
	}

	UE_LOG(LogTemp, Log, TEXT("Water: Feature generated at level %.1f"), WaterLevel);
}

void AWorldManager::GenerateStreetFurniture()
{
	const FLinearColor BenchColor(0.392f, 0.275f, 0.157f);
	const FLinearColor LamppostColor(0.314f, 0.314f, 0.333f);
	const FLinearColor HydrantColor(0.784f, 0.157f, 0.118f);
	const FLinearColor TrashColor(0.275f, 0.275f, 0.294f);
	const FLinearColor LampLightColor(1.0f, 0.941f, 0.784f);

	const float HalfRoad = RoadWidth * 0.5f;
	const float HalfLen = RoadLength * 0.5f;
	const float Spacing = 25.0f;

	for (float Dist = -HalfLen + 15.0f; Dist < HalfLen; Dist += Spacing)
	{
		const float LX1 = Dist;
		const float LY1 = HalfRoad + SidewalkWidth * 0.5f;
		const float LBaseY1 = ComputeTerrainHeight(LX1, LY1);
		AddCylinderMesh(StreetFurnitureMesh, FVector(LX1, LY1, LBaseY1 + 2.0f),
			0.08f, 4.0f, LamppostColor, 8);
		AddBoxMesh(StreetFurnitureMesh, FVector(LX1, LY1, LBaseY1 + 4.1f),
			FVector(0.5f, 0.3f, 0.15f), LampLightColor);

		const float LX2 = Dist;
		const float LY2 = -(HalfRoad + SidewalkWidth * 0.5f);
		const float LBaseY2 = ComputeTerrainHeight(LX2, LY2);
		AddCylinderMesh(StreetFurnitureMesh, FVector(LX2, LY2, LBaseY2 + 2.0f),
			0.08f, 4.0f, LamppostColor, 8);
		AddBoxMesh(StreetFurnitureMesh, FVector(LX2, LY2, LBaseY2 + 4.1f),
			FVector(0.5f, 0.3f, 0.15f), LampLightColor);

		const float LX3 = HalfRoad + SidewalkWidth * 0.5f;
		const float LY3 = Dist;
		const float LBaseY3 = ComputeTerrainHeight(LX3, LY3);
		AddCylinderMesh(StreetFurnitureMesh, FVector(LX3, LY3, LBaseY3 + 2.0f),
			0.08f, 4.0f, LamppostColor, 8);
		AddBoxMesh(StreetFurnitureMesh, FVector(LX3, LY3, LBaseY3 + 4.1f),
			FVector(0.3f, 0.5f, 0.15f), LampLightColor);

		if (FMath::Fmod(Dist, Spacing * 2) < 0.1f)
		{
			const float BX = Dist + 8.0f;
			const float BY = HalfRoad + SidewalkWidth * 0.7f;
			const float BBaseY = ComputeTerrainHeight(BX, BY);
			AddBoxMesh(StreetFurnitureMesh, FVector(BX, BY, BBaseY + 0.25f),
				FVector(0.8f, 0.35f, 0.05f), BenchColor);
			AddBoxMesh(StreetFurnitureMesh, FVector(BX, BY - 0.3f, BBaseY + 0.5f),
				FVector(0.8f, 0.05f, 0.25f), BenchColor);
		}

		if (FMath::Fmod(Dist + 10.0f, Spacing * 3) < 0.1f)
		{
			const float HX = Dist + 12.0f;
			const float HY = HalfRoad + SidewalkWidth * 0.3f;
			const float HBaseY = ComputeTerrainHeight(HX, HY);
			AddCylinderMesh(StreetFurnitureMesh, FVector(HX, HY, HBaseY + 0.35f),
				0.15f, 0.7f, HydrantColor, 8);
		}

		if (FMath::Fmod(Dist + 5.0f, Spacing * 4) < 0.1f)
		{
			const float TX = Dist + 5.0f;
			const float TY = -(HalfRoad + SidewalkWidth * 0.4f);
			const float TBaseY = ComputeTerrainHeight(TX, TY);
			AddCylinderMesh(StreetFurnitureMesh, FVector(TX, TY, TBaseY + 0.3f),
				0.2f, 0.6f, TrashColor, 8);
		}
	}

	UE_LOG(LogTemp, Log, TEXT("Street furniture: Generated along roads"));
}

void AWorldManager::AddBoxMesh(UProceduralMeshComponent* Mesh, const FVector& Center, const FVector& BoxExtent, const FLinearColor& Color)
{
	const float X = BoxExtent.X;
	const float Y = BoxExtent.Y;
	const float Z = BoxExtent.Z;

	TArray<FVector> Vertices = {
		FVector(-X, -Y, -Z), FVector( X, -Y, -Z), FVector( X,  Y, -Z), FVector(-X,  Y, -Z),
		FVector(-X, -Y,  Z), FVector( X, -Y,  Z), FVector( X,  Y,  Z), FVector(-X,  Y,  Z),
		FVector(-X, -Y, -Z), FVector( X, -Y, -Z), FVector( X, -Y,  Z), FVector(-X, -Y,  Z),
		FVector( X, -Y, -Z), FVector( X,  Y, -Z), FVector( X,  Y,  Z), FVector( X, -Y,  Z),
		FVector( X,  Y, -Z), FVector(-X,  Y, -Z), FVector(-X,  Y,  Z), FVector( X,  Y,  Z),
		FVector(-X,  Y, -Z), FVector(-X, -Y, -Z), FVector(-X, -Y,  Z), FVector(-X,  Y,  Z),
	};

	for (FVector& V : Vertices)
	{
		V += Center;
	}

	TArray<int32> Triangles = {
		0, 2, 1, 0, 3, 2,
		4, 5, 6, 4, 6, 7,
		8, 9, 10, 8, 10, 11,
		12, 13, 14, 12, 14, 15,
		16, 17, 18, 16, 18, 19,
		20, 21, 22, 20, 22, 23,
	};

	TArray<FVector> Normals = {
		FVector(0, 0, -1), FVector(0, 0, -1), FVector(0, 0, -1), FVector(0, 0, -1),
		FVector(0, 0, 1), FVector(0, 0, 1), FVector(0, 0, 1), FVector(0, 0, 1),
		FVector(0, -1, 0), FVector(0, -1, 0), FVector(0, -1, 0), FVector(0, -1, 0),
		FVector(1, 0, 0), FVector(1, 0, 0), FVector(1, 0, 0), FVector(1, 0, 0),
		FVector(0, 1, 0), FVector(0, 1, 0), FVector(0, 1, 0), FVector(0, 1, 0),
		FVector(-1, 0, 0), FVector(-1, 0, 0), FVector(-1, 0, 0), FVector(-1, 0, 0),
	};

	TArray<FVector2D> UVs = {
		FVector2D(0, 0), FVector2D(1, 0), FVector2D(1, 1), FVector2D(0, 1),
		FVector2D(0, 0), FVector2D(1, 0), FVector2D(1, 1), FVector2D(0, 1),
		FVector2D(0, 0), FVector2D(1, 0), FVector2D(1, 1), FVector2D(0, 1),
		FVector2D(0, 0), FVector2D(1, 0), FVector2D(1, 1), FVector2D(0, 1),
		FVector2D(0, 0), FVector2D(1, 0), FVector2D(1, 1), FVector2D(0, 1),
		FVector2D(0, 0), FVector2D(1, 0), FVector2D(1, 1), FVector2D(0, 1),
	};

	TArray<FLinearColor> LinColors = {
		Color, Color, Color, Color, Color, Color, Color, Color,
		Color, Color, Color, Color, Color, Color, Color, Color,
		Color, Color, Color, Color, Color, Color, Color, Color,
	};

	const int32 SectionIdx = Mesh->GetNumSections();
	Mesh->CreateMeshSection_LinearColor(SectionIdx, Vertices, Triangles, Normals, UVs, LinColors,
		TArray<FProcMeshTangent>(), false);
}

void AWorldManager::AddCylinderMesh(UProceduralMeshComponent* Mesh, const FVector& Center, float Radius, float Height, const FLinearColor& Color, int32 Segments)
{
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UVs;
	TArray<FLinearColor> LinColors;

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		const float X = FMath::Cos(Angle) * Radius;
		const float Y = FMath::Sin(Angle) * Radius;
		const float U = static_cast<float>(i) / Segments;

		Vertices.Add(FVector(Center.X + X, Center.Y + Y, Center.Z - Height * 0.5f));
		Normals.Add(FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0));
		UVs.Add(FVector2D(U, 0));
		LinColors.Add(Color);

		Vertices.Add(FVector(Center.X + X, Center.Y + Y, Center.Z + Height * 0.5f));
		Normals.Add(FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0));
		UVs.Add(FVector2D(U, 1));
		LinColors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		const int32 Base = i * 2;
		Triangles.Add(Base); Triangles.Add(Base + 2); Triangles.Add(Base + 1);
		Triangles.Add(Base + 1); Triangles.Add(Base + 2); Triangles.Add(Base + 3);
	}

	const int32 TopCenter = Vertices.Num();
	Vertices.Add(FVector(Center.X, Center.Y, Center.Z + Height * 0.5f));
	Normals.Add(FVector(0, 0, 1));
	UVs.Add(FVector2D(0.5f, 0.5f));
	LinColors.Add(Color);

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		Vertices.Add(FVector(Center.X + FMath::Cos(Angle) * Radius, Center.Y + FMath::Sin(Angle) * Radius, Center.Z + Height * 0.5f));
		Normals.Add(FVector(0, 0, 1));
		UVs.Add(FVector2D(FMath::Cos(Angle) * 0.5f + 0.5f, FMath::Sin(Angle) * 0.5f + 0.5f));
		LinColors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		Triangles.Add(TopCenter);
		Triangles.Add(TopCenter + 1 + i);
		Triangles.Add(TopCenter + 1 + i + 1);
	}

	const int32 BotCenter = Vertices.Num();
	Vertices.Add(FVector(Center.X, Center.Y, Center.Z - Height * 0.5f));
	Normals.Add(FVector(0, 0, -1));
	UVs.Add(FVector2D(0.5f, 0.5f));
	LinColors.Add(Color);

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		Vertices.Add(FVector(Center.X + FMath::Cos(Angle) * Radius, Center.Y + FMath::Sin(Angle) * Radius, Center.Z - Height * 0.5f));
		Normals.Add(FVector(0, 0, -1));
		UVs.Add(FVector2D(FMath::Cos(Angle) * 0.5f + 0.5f, FMath::Sin(Angle) * 0.5f + 0.5f));
		LinColors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		Triangles.Add(BotCenter);
		Triangles.Add(BotCenter + 1 + i + 1);
		Triangles.Add(BotCenter + 1 + i);
	}

	const int32 SectionIdx = Mesh->GetNumSections();
	Mesh->CreateMeshSection_LinearColor(SectionIdx, Vertices, Triangles, Normals, UVs, LinColors,
		TArray<FProcMeshTangent>(), false);
}

void AWorldManager::AddConeMesh(UProceduralMeshComponent* Mesh, const FVector& Center, float Radius, float Height, const FLinearColor& Color, int32 Segments)
{
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UVs;
	TArray<FLinearColor> LinColors;

	const FVector Tip(Center.X, Center.Y, Center.Z + Height);

	Vertices.Add(Tip);
	Normals.Add(FVector(0, 0, 1));
	UVs.Add(FVector2D(0.5f, 1.0f));
	LinColors.Add(Color);

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		const float X = FMath::Cos(Angle) * Radius;
		const float Y = FMath::Sin(Angle) * Radius;

		const FVector P(Center.X + X, Center.Y + Y, Center.Z);
		const FVector Normal = FVector(X, Y, Radius * 0.3f).GetSafeNormal();

		Vertices.Add(P);
		Normals.Add(Normal);
		UVs.Add(FVector2D(static_cast<float>(i) / Segments, 0));
		LinColors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		Triangles.Add(0);
		Triangles.Add(1 + i);
		Triangles.Add(1 + i + 1);
	}

	const int32 BaseCenter = Vertices.Num();
	Vertices.Add(FVector(Center.X, Center.Y, Center.Z));
	Normals.Add(FVector(0, 0, -1));
	UVs.Add(FVector2D(0.5f, 0.5f));
	LinColors.Add(Color);

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		Vertices.Add(FVector(Center.X + FMath::Cos(Angle) * Radius, Center.Y + FMath::Sin(Angle) * Radius, Center.Z));
		Normals.Add(FVector(0, 0, -1));
		UVs.Add(FVector2D(FMath::Cos(Angle) * 0.5f + 0.5f, FMath::Sin(Angle) * 0.5f + 0.5f));
		LinColors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		Triangles.Add(BaseCenter);
		Triangles.Add(BaseCenter + 1 + i + 1);
		Triangles.Add(BaseCenter + 1 + i);
	}

	const int32 SectionIdx = Mesh->GetNumSections();
	Mesh->CreateMeshSection_LinearColor(SectionIdx, Vertices, Triangles, Normals, UVs, LinColors,
		TArray<FProcMeshTangent>(), false);
}

void AWorldManager::SetupLightingAndPostProcess()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	ADirectionalLight* SunLight = World->SpawnActor<ADirectionalLight>(
		ADirectionalLight::StaticClass(),
		FVector(0, 0, 500),
		FRotator(-45, 30, 0),
		SpawnParams);

	if (SunLight)
	{
		ULightComponent* LightComp = SunLight->GetLightComponent();
		LightComp->SetIntensity(15.0f);
		LightComp->SetLightColor(FLinearColor(1.0f, 0.95f, 0.85f));
		LightComp->SetCastShadows(true);
		LightComp->SetShadowBias(0.5f);
		LightComp->SetShadowSlopeBias(0.5f);
		UE_LOG(LogTemp, Log, TEXT("Sun light created"));
	}

	ASkyLight* SkyLight = World->SpawnActor<ASkyLight>(
		ASkyLight::StaticClass(),
		FVector(0, 0, 200),
		FRotator::ZeroRotator,
		SpawnParams);

	if (SkyLight)
	{
		UE_LOG(LogTemp, Log, TEXT("Sky light created"));
	}

	AExponentialHeightFog* Fog = World->SpawnActor<AExponentialHeightFog>(
		AExponentialHeightFog::StaticClass(),
		FVector::ZeroVector,
		FRotator::ZeroRotator,
		SpawnParams);

	if (Fog)
	{
		UExponentialHeightFogComponent* FogComp = Fog->GetComponent();
		FogComp->SetFogDensity(0.001f);
		FogComp->SetFogInscatteringColor(FLinearColor(0.7f, 0.8f, 0.95f));
		FogComp->SetDirectionalInscatteringColor(FLinearColor(1.0f, 0.95f, 0.85f));
		FogComp->SetFogHeightFalloff(0.1f);
		UE_LOG(LogTemp, Log, TEXT("Height fog created"));
	}

	APostProcessVolume* PostProcess = World->SpawnActor<APostProcessVolume>(
		APostProcessVolume::StaticClass(),
		FVector::ZeroVector,
		FRotator::ZeroRotator,
		SpawnParams);

	if (PostProcess)
	{
		PostProcess->bUnbound = true;

		FPostProcessSettings& Settings = PostProcess->Settings;

		Settings.bOverride_BloomIntensity = true;
		Settings.BloomIntensity = 0.4f;
		Settings.bOverride_BloomThreshold = true;
		Settings.BloomThreshold = 0.8f;

		Settings.bOverride_AutoExposureMinBrightness = true;
		Settings.AutoExposureMinBrightness = 0.3f;
		Settings.bOverride_AutoExposureMaxBrightness = true;
		Settings.AutoExposureMaxBrightness = 4.0f;

		Settings.bOverride_ColorSaturation = true;
		Settings.ColorSaturation = FVector4(1.3f, 1.3f, 1.3f, 1.0f);

		Settings.bOverride_ColorContrast = true;
		Settings.ColorContrast = FVector4(1.15f, 1.15f, 1.15f, 1.0f);

		Settings.bOverride_VignetteIntensity = true;
		Settings.VignetteIntensity = 0.3f;

		Settings.bOverride_MotionBlurAmount = true;
		Settings.MotionBlurAmount = 0.0f;

		Settings.bOverride_ToneCurveAmount = true;
		Settings.ToneCurveAmount = 1.0f;

		UE_LOG(LogTemp, Log, TEXT("Post-process volume created: bloom=0.4, saturation=1.3, contrast=1.15, vignette=0.3"));
	}
}

void AWorldManager::CreateVertexColorMaterial()
{
	if (VertexColorMaterial)
	{
		return;
	}

	VertexColorMaterial = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/Materials/M_VertexColor.M_VertexColor"));

	if (VertexColorMaterial)
	{
		UE_LOG(LogTemp, Log, TEXT("Vertex color material loaded from asset"));
		return;
	}

	UE_LOG(LogTemp, Warning, TEXT("M_VertexColor asset not found. Run CreateVertexColorMaterial.py in editor."));

	VertexColorMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
}

void AWorldManager::ApplyMaterialToAllMeshes()
{
	if (!VertexColorMaterial)
	{
		UE_LOG(LogTemp, Warning, TEXT("No vertex color material available"));
		return;
	}

	TArray<UProceduralMeshComponent*> Meshes;
	Meshes.Add(TerrainMesh);
	Meshes.Add(RoadMesh);
	Meshes.Add(BuildingMesh);
	Meshes.Add(TreeMesh);
	Meshes.Add(MountainMesh);
	Meshes.Add(WaterMesh);
	Meshes.Add(StreetFurnitureMesh);

	for (UProceduralMeshComponent* Mesh : Meshes)
	{
		if (Mesh)
		{
			const int32 NumSections = Mesh->GetNumSections();
			for (int32 i = 0; i < NumSections; i++)
			{
				Mesh->SetMaterial(i, VertexColorMaterial);
			}
		}
	}

	UE_LOG(LogTemp, Log, TEXT("Applied vertex color material to all procedural meshes"));
}

void AWorldManager::SetupMiamiSunsetLighting()
{
}
