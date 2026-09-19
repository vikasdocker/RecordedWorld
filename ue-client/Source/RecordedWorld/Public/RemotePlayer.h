#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProceduralMeshComponent.h"
#include "RemotePlayer.generated.h"

class UPlayerNameBillboard;

UCLASS()
class RECORDEDWORLD_API ARemotePlayer : public AActor
{
	GENERATED_BODY()

public:
	ARemotePlayer();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaTime) override;

	void InitPlayer(const FString& InUsername, const FLinearColor& InColor);
	void UpdatePosition(const FVector& NewPosition, float NewRotation);
	void UpdateColor(const FLinearColor& NewColor);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player")
	FString Username;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player")
	int32 ServerPlayerId = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Components")
	TObjectPtr<USceneComponent> BodyRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Body")
	TObjectPtr<UProceduralMeshComponent> TorsoMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Body")
	TObjectPtr<UProceduralMeshComponent> HeadMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Body")
	TObjectPtr<UProceduralMeshComponent> LeftArmMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Body")
	TObjectPtr<UProceduralMeshComponent> RightArmMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Body")
	TObjectPtr<UProceduralMeshComponent> LeftLegMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Body")
	TObjectPtr<UProceduralMeshComponent> RightLegMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player|Components")
	TObjectPtr<UPlayerNameBillboard> NameBillboard;

private:
	void BuildBody(const FLinearColor& ShirtColor);
	void ApplyBodyMaterial();
	void AddMeshBox(UProceduralMeshComponent* Comp, const FVector& Size, const FLinearColor& Color);
	void AddMeshSphere(UProceduralMeshComponent* Comp, float Radius, const FLinearColor& Color, int32 Segments = 10);

	FVector TargetPosition;
	float TargetRotation = 0.0f;
	float CurrentRotation = 0.0f;
	float LerpSpeed = 10.0f;
	float AnimTime = 0.0f;

	static constexpr float PlayerHeight = 1.7f;
	static constexpr float BodyWidth = 0.3f;
};
