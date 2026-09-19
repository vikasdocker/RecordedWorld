#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProceduralMeshComponent.h"
#include "WorldManager.generated.h"

UCLASS()
class RECORDEDWORLD_API AWorldManager : public AActor
{
	GENERATED_BODY()

public:
	AWorldManager();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "World")
	float GetTerrainHeight(float X, float Z) const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Terrain")
	float TerrainSize = 400.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Terrain")
	int32 TerrainSegments = 128;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Terrain")
	float MaxTerrainHeight = 8.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Roads")
	float RoadWidth = 5.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Roads")
	float SidewalkWidth = 1.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Roads")
	float RoadLength = 300.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Buildings")
	int32 BuildingGridSpacing = 16;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Buildings")
	int32 BuildingGridExtent = 5;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Trees")
	int32 TreeClusterCount = 12;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Trees")
	int32 TreesPerCluster = 15;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Mountains")
	float MountainHeight = 40.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Mountains")
	float MountainStartRadius = 160.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Water")
	float WaterLevel = -0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World|Water")
	float WaterSize = 30.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> TerrainMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> RoadMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> BuildingMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> TreeMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> MountainMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> WaterMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "World|Components")
	TObjectPtr<UProceduralMeshComponent> StreetFurnitureMesh;

private:
	void GenerateTerrain();
	void GenerateRoads();
	void GenerateBuildings();
	void GenerateTrees();
	void GenerateMountains();
	void GenerateWaterFeature();
	void GenerateStreetFurniture();

	float ComputeTerrainHeight(float X, float Z) const;

	void AddBoxMesh(UProceduralMeshComponent* Mesh, const FVector& Center, const FVector& BoxExtent, const FLinearColor& Color);
	void AddCylinderMesh(UProceduralMeshComponent* Mesh, const FVector& Center, float Radius, float Height, const FLinearColor& Color, int32 Segments = 12);
	void AddConeMesh(UProceduralMeshComponent* Mesh, const FVector& Center, float Radius, float Height, const FLinearColor& Color, int32 Segments = 12);

	void SetupLightingAndPostProcess();
	void SetupMiamiSunsetLighting();

	void CreateVertexColorMaterial();
	void ApplyMaterialToAllMeshes();

	UPROPERTY()
	TObjectPtr<UMaterialInterface> VertexColorMaterial;
};
