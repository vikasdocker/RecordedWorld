#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "ProceduralMeshComponent.h"
#include "RWCharacter.generated.h"

class USpringArmComponent;
class UCameraComponent;

UENUM(BlueprintType)
enum class EPlayerAnimState : uint8
{
	Idle,
	Walk,
	Run
};

UCLASS()
class RECORDEDWORLD_API ARWCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ARWCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaTime) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character")
	EPlayerAnimState AnimState = EPlayerAnimState::Idle;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	float PlayerHeight = 1.7f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	float BodyWidth = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	FLinearColor SkinColor = FLinearColor(1.0f, 0.86f, 0.67f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	FLinearColor ShirtColor = FLinearColor(0.0f, 1.0f, 0.53f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	FLinearColor PantsColor = FLinearColor(0.165f, 0.2f, 0.267f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	FLinearColor ShoeColor = FLinearColor(0.1f, 0.1f, 0.1f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Character|Appearance")
	FLinearColor HairColor = FLinearColor(0.165f, 0.102f, 0.039f);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Components")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Components")
	TObjectPtr<UCameraComponent> FollowCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<USceneComponent> BodyRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> TorsoMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> HeadMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> HairMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> LeftArmMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> RightArmMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> LeftHandMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> RightHandMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> LeftLegMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> RightLegMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> LeftShoeMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> RightShoeMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> NeckMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> EyeWhiteLeftMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> EyeWhiteRightMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> EyeIrisLeftMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> EyeIrisRightMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> NoseMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Character|Body")
	TObjectPtr<UProceduralMeshComponent> MouthMesh;

private:
	void BuildBodyParts();
	void ApplyBodyMaterial();
	void AddMeshBox(UProceduralMeshComponent* Comp, const FVector& Size, const FLinearColor& Color);
	void AddMeshSphere(UProceduralMeshComponent* Comp, float Radius, const FLinearColor& Color, int32 Segments = 12);
	void AddMeshCylinder(UProceduralMeshComponent* Comp, float Radius, float Height, const FLinearColor& Color, int32 Segments = 10);

	void UpdateAnimation(float DeltaTime);

	float AnimTime = 0.0f;
	float LeftArmAngle = 0.0f;
	float RightArmAngle = 0.0f;
	float LeftLegAngle = 0.0f;
	float RightLegAngle = 0.0f;

	static constexpr float ArmSwingSpeed = 8.0f;
	static constexpr float ArmSwingAmplitude = 0.5f;
	static constexpr float LegSwingSpeed = 8.0f;
	static constexpr float LegSwingAmplitude = 0.45f;
	static constexpr float WalkBobSpeed = 10.0f;
	static constexpr float WalkBobAmount = 0.015f;
	static constexpr float RunBobAmount = 0.03f;
};
