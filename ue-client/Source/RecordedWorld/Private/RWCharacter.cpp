#include "RWCharacter.h"
#include "GameFramework/SpringArmComponent.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/CapsuleComponent.h"
#include "Materials/Material.h"

ARWCharacter::ARWCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->SetCapsuleHalfHeight(0.9f);
	GetCapsuleComponent()->SetCapsuleRadius(0.3f);

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 4.0f;
	CameraBoom->SocketOffset = FVector(0.0f, 0.0f, 60.0f);
	CameraBoom->bUsePawnControlRotation = true;
	CameraBoom->bDoCollisionTest = true;
	CameraBoom->ProbeSize = 12.0f;
	CameraBoom->ProbeChannel = ECC_Camera;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;

	BodyRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BodyRoot"));
	BodyRoot->SetupAttachment(GetCapsuleComponent());
	BodyRoot->SetRelativeLocation(FVector(0.0f, 0.0f, -88.0f));

	TorsoMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("TorsoMesh"));
	TorsoMesh->SetupAttachment(BodyRoot);
	HeadMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("HeadMesh"));
	HeadMesh->SetupAttachment(BodyRoot);
	HairMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("HairMesh"));
	HairMesh->SetupAttachment(BodyRoot);
	LeftArmMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("LeftArmMesh"));
	LeftArmMesh->SetupAttachment(BodyRoot);
	RightArmMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RightArmMesh"));
	RightArmMesh->SetupAttachment(BodyRoot);
	LeftHandMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("LeftHandMesh"));
	LeftHandMesh->SetupAttachment(BodyRoot);
	RightHandMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RightHandMesh"));
	RightHandMesh->SetupAttachment(BodyRoot);
	LeftLegMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("LeftLegMesh"));
	LeftLegMesh->SetupAttachment(BodyRoot);
	RightLegMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RightLegMesh"));
	RightLegMesh->SetupAttachment(BodyRoot);
	LeftShoeMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("LeftShoeMesh"));
	LeftShoeMesh->SetupAttachment(BodyRoot);
	RightShoeMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RightShoeMesh"));
	RightShoeMesh->SetupAttachment(BodyRoot);
	NeckMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("NeckMesh"));
	NeckMesh->SetupAttachment(BodyRoot);
	EyeWhiteLeftMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("EyeWhiteLeft"));
	EyeWhiteLeftMesh->SetupAttachment(BodyRoot);
	EyeWhiteRightMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("EyeWhiteRight"));
	EyeWhiteRightMesh->SetupAttachment(BodyRoot);
	EyeIrisLeftMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("EyeIrisLeft"));
	EyeIrisLeftMesh->SetupAttachment(BodyRoot);
	EyeIrisRightMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("EyeIrisRight"));
	EyeIrisRightMesh->SetupAttachment(BodyRoot);
	NoseMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("NoseMesh"));
	NoseMesh->SetupAttachment(BodyRoot);
	MouthMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("MouthMesh"));
	MouthMesh->SetupAttachment(BodyRoot);

	UCharacterMovementComponent* MoveComp = GetCharacterMovement();
	MoveComp->MaxWalkSpeed = 600.0f;
	MoveComp->MaxWalkSpeedCrouched = 300.0f;
	MoveComp->GravityScale = 1.5f;
	MoveComp->JumpZVelocity = 420.0f;
	MoveComp->AirControl = 0.2f;
	MoveComp->BrakingDecelerationWalking = 2000.0f;
	MoveComp->BrakingDecelerationFalling = 200.0f;
}

void ARWCharacter::BeginPlay()
{
	Super::BeginPlay();
	BuildBodyParts();
	ApplyBodyMaterial();
	UE_LOG(LogTemp, Log, TEXT("RWCharacter: Body parts built"));
}

void ARWCharacter::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	UpdateAnimation(DeltaTime);
}

void ARWCharacter::BuildBodyParts()
{
	const float BW = BodyWidth;
	const float PH = PlayerHeight;

	AddMeshBox(TorsoMesh, FVector(BW * 0.5f, 0.09f, 0.26f), ShirtColor);
	TorsoMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.65f));

	AddMeshSphere(HeadMesh, 0.13f, SkinColor, 14);
	HeadMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.91f));

	AddMeshSphere(HairMesh, 0.14f, HairColor, 12);
	HairMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.92f));

	AddMeshCylinder(NeckMesh, 0.065f, 0.12f, SkinColor, 8);
	NeckMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.81f));

	AddMeshBox(LeftArmMesh, FVector(0.045f, 0.045f, 0.21f), ShirtColor);
	LeftArmMesh->SetRelativeLocation(FVector(-BW * 0.5f - 0.065f, 0.0f, PH * 0.75f));

	AddMeshBox(RightArmMesh, FVector(0.045f, 0.045f, 0.21f), ShirtColor);
	RightArmMesh->SetRelativeLocation(FVector(BW * 0.5f + 0.065f, 0.0f, PH * 0.75f));

	AddMeshSphere(LeftHandMesh, 0.045f, SkinColor, 8);
	LeftHandMesh->SetRelativeLocation(FVector(-BW * 0.5f - 0.065f, 0.0f, PH * 0.53f));

	AddMeshSphere(RightHandMesh, 0.045f, SkinColor, 8);
	RightHandMesh->SetRelativeLocation(FVector(BW * 0.5f + 0.065f, 0.0f, PH * 0.53f));

	AddMeshBox(LeftLegMesh, FVector(0.055f, 0.055f, 0.24f), PantsColor);
	LeftLegMesh->SetRelativeLocation(FVector(-0.08f, 0.0f, PH * 0.28f));

	AddMeshBox(RightLegMesh, FVector(0.055f, 0.055f, 0.24f), PantsColor);
	RightLegMesh->SetRelativeLocation(FVector(0.08f, 0.0f, PH * 0.28f));

	AddMeshBox(LeftShoeMesh, FVector(0.06f, 0.085f, 0.035f), ShoeColor);
	LeftShoeMesh->SetRelativeLocation(FVector(-0.08f, 0.02f, PH * 0.02f));

	AddMeshBox(RightShoeMesh, FVector(0.06f, 0.085f, 0.035f), ShoeColor);
	RightShoeMesh->SetRelativeLocation(FVector(0.08f, 0.02f, PH * 0.02f));

	AddMeshSphere(EyeWhiteLeftMesh, 0.025f, FLinearColor(0.97f, 0.97f, 0.97f), 8);
	EyeWhiteLeftMesh->SetRelativeLocation(FVector(-0.045f, 0.065f, PH * 0.91f));

	AddMeshSphere(EyeWhiteRightMesh, 0.025f, FLinearColor(0.97f, 0.97f, 0.97f), 8);
	EyeWhiteRightMesh->SetRelativeLocation(FVector(0.045f, 0.065f, PH * 0.91f));

	AddMeshSphere(EyeIrisLeftMesh, 0.015f, FLinearColor(0.227f, 0.165f, 0.102f), 8);
	EyeIrisLeftMesh->SetRelativeLocation(FVector(-0.045f, 0.075f, PH * 0.91f));

	AddMeshSphere(EyeIrisRightMesh, 0.015f, FLinearColor(0.227f, 0.165f, 0.102f), 8);
	EyeIrisRightMesh->SetRelativeLocation(FVector(0.045f, 0.075f, PH * 0.91f));

	AddMeshSphere(NoseMesh, 0.02f, SkinColor, 6);
	NoseMesh->SetRelativeLocation(FVector(0.0f, 0.065f, PH * 0.88f));

	AddMeshBox(MouthMesh, FVector(0.025f, 0.005f, 0.005f), FLinearColor(0.8f, 0.533f, 0.467f));
	MouthMesh->SetRelativeLocation(FVector(0.0f, 0.065f, PH * 0.865f));
}

void ARWCharacter::ApplyBodyMaterial()
{
	UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/Materials/M_VertexColor.M_VertexColor"));

	if (!Mat)
	{
		Mat = UMaterial::GetDefaultMaterial(MD_Surface);
	}

	TArray<UProceduralMeshComponent*> BodyMeshes = {
		TorsoMesh, HeadMesh, HairMesh, NeckMesh,
		LeftArmMesh, RightArmMesh, LeftHandMesh, RightHandMesh,
		LeftLegMesh, RightLegMesh, LeftShoeMesh, RightShoeMesh,
		EyeWhiteLeftMesh, EyeWhiteRightMesh, EyeIrisLeftMesh, EyeIrisRightMesh,
		NoseMesh, MouthMesh
	};

	for (UProceduralMeshComponent* BodyPart : BodyMeshes)
	{
		if (BodyPart)
		{
			BodyPart->SetMaterial(0, Mat);
		}
	}

	UE_LOG(LogTemp, Log, TEXT("RWCharacter: Vertex color material applied to body"));
}

void ARWCharacter::AddMeshBox(UProceduralMeshComponent* Comp, const FVector& Size, const FLinearColor& Color)
{
	const float X = Size.X;
	const float Y = Size.Y;
	const float Z = Size.Z;

	TArray<FVector> Vertices = {
		FVector(-X, -Y, -Z), FVector( X, -Y, -Z), FVector( X,  Y, -Z), FVector(-X,  Y, -Z),
		FVector(-X, -Y,  Z), FVector( X, -Y,  Z), FVector( X,  Y,  Z), FVector(-X,  Y,  Z),
		FVector(-X, -Y, -Z), FVector( X, -Y, -Z), FVector( X, -Y,  Z), FVector(-X, -Y,  Z),
		FVector( X, -Y, -Z), FVector( X,  Y, -Z), FVector( X,  Y,  Z), FVector( X, -Y,  Z),
		FVector( X,  Y, -Z), FVector(-X,  Y, -Z), FVector(-X,  Y,  Z), FVector( X,  Y,  Z),
		FVector(-X,  Y, -Z), FVector(-X, -Y, -Z), FVector(-X, -Y,  Z), FVector(-X,  Y,  Z),
	};

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

	TArray<FLinearColor> Colors;
	for (int32 i = 0; i < 24; i++) Colors.Add(Color);

	Comp->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors,
		TArray<FProcMeshTangent>(), false);
}

void ARWCharacter::AddMeshSphere(UProceduralMeshComponent* Comp, float Radius, const FLinearColor& Color, int32 Segments)
{
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UVs;
	TArray<FLinearColor> Colors;

	const int32 Rings = Segments;
	const int32 Sectors = Segments;

	for (int32 r = 0; r <= Rings; r++)
	{
		const float Phi = PI * r / Rings;
		const float SinPhi = FMath::Sin(Phi);
		const float CosPhi = FMath::Cos(Phi);

		for (int32 s = 0; s <= Sectors; s++)
		{
			const float Theta = 2.0f * PI * s / Sectors;
			const float X = SinPhi * FMath::Cos(Theta) * Radius;
			const float Y = SinPhi * FMath::Sin(Theta) * Radius;
			const float Z = CosPhi * Radius;

			Vertices.Add(FVector(X, Y, Z));
			Normals.Add(FVector(X, Y, Z).GetSafeNormal());
			UVs.Add(FVector2D(static_cast<float>(s) / Sectors, static_cast<float>(r) / Rings));
			Colors.Add(Color);
		}
	}

	for (int32 r = 0; r < Rings; r++)
	{
		for (int32 s = 0; s < Sectors; s++)
		{
			const int32 I0 = r * (Sectors + 1) + s;
			const int32 I1 = I0 + 1;
			const int32 I2 = (r + 1) * (Sectors + 1) + s;
			const int32 I3 = I2 + 1;

			Triangles.Add(I0);
			Triangles.Add(I2);
			Triangles.Add(I1);
			Triangles.Add(I1);
			Triangles.Add(I2);
			Triangles.Add(I3);
		}
	}

	Comp->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors,
		TArray<FProcMeshTangent>(), false);
}

void ARWCharacter::AddMeshCylinder(UProceduralMeshComponent* Comp, float Radius, float Height, const FLinearColor& Color, int32 Segments)
{
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UVs;
	TArray<FLinearColor> Colors;

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		const float X = FMath::Cos(Angle) * Radius;
		const float Y = FMath::Sin(Angle) * Radius;
		const float U = static_cast<float>(i) / Segments;

		Vertices.Add(FVector(X, Y, -Height * 0.5f));
		Normals.Add(FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0));
		UVs.Add(FVector2D(U, 0));
		Colors.Add(Color);

		Vertices.Add(FVector(X, Y, Height * 0.5f));
		Normals.Add(FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0));
		UVs.Add(FVector2D(U, 1));
		Colors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		const int32 Base = i * 2;
		Triangles.Add(Base); Triangles.Add(Base + 2); Triangles.Add(Base + 1);
		Triangles.Add(Base + 1); Triangles.Add(Base + 2); Triangles.Add(Base + 3);
	}

	const int32 TopCenter = Vertices.Num();
	Vertices.Add(FVector(0, 0, Height * 0.5f));
	Normals.Add(FVector(0, 0, 1));
	UVs.Add(FVector2D(0.5f, 0.5f));
	Colors.Add(Color);

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		Vertices.Add(FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, Height * 0.5f));
		Normals.Add(FVector(0, 0, 1));
		UVs.Add(FVector2D(FMath::Cos(Angle) * 0.5f + 0.5f, FMath::Sin(Angle) * 0.5f + 0.5f));
		Colors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		Triangles.Add(TopCenter);
		Triangles.Add(TopCenter + 1 + i);
		Triangles.Add(TopCenter + 1 + i + 1);
	}

	const int32 BottomCenter = Vertices.Num();
	Vertices.Add(FVector(0, 0, -Height * 0.5f));
	Normals.Add(FVector(0, 0, -1));
	UVs.Add(FVector2D(0.5f, 0.5f));
	Colors.Add(Color);

	for (int32 i = 0; i <= Segments; i++)
	{
		const float Angle = i * 2.0f * PI / Segments;
		Vertices.Add(FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, -Height * 0.5f));
		Normals.Add(FVector(0, 0, -1));
		UVs.Add(FVector2D(FMath::Cos(Angle) * 0.5f + 0.5f, FMath::Sin(Angle) * 0.5f + 0.5f));
		Colors.Add(Color);
	}

	for (int32 i = 0; i < Segments; i++)
	{
		Triangles.Add(BottomCenter);
		Triangles.Add(BottomCenter + 1 + i + 1);
		Triangles.Add(BottomCenter + 1 + i);
	}

	Comp->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors,
		TArray<FProcMeshTangent>(), false);
}

void ARWCharacter::UpdateAnimation(float DeltaTime)
{
	const FVector Velocity = GetVelocity();
	const float Speed = FVector(Velocity.X, Velocity.Y, 0.0f).Size();

	EPlayerAnimState TargetState;
	if (Speed < 50.0f)
	{
		TargetState = EPlayerAnimState::Idle;
	}
	else if (Speed < 350.0f)
	{
		TargetState = EPlayerAnimState::Walk;
	}
	else
	{
		TargetState = EPlayerAnimState::Run;
	}

	AnimState = TargetState;

	const float SpeedFactor = (AnimState == EPlayerAnimState::Idle) ? 0.0f :
		(AnimState == EPlayerAnimState::Walk) ? 0.5f : 1.0f;

	AnimTime += DeltaTime * SpeedFactor;

	const float ArmSwing = FMath::Sin(AnimTime * ArmSwingSpeed) * ArmSwingAmplitude * SpeedFactor;
	const float LegSwing = FMath::Sin(AnimTime * LegSwingSpeed) * LegSwingAmplitude * SpeedFactor;
	const float Bob = (AnimState == EPlayerAnimState::Idle) ? 0.0f :
		FMath::Sin(AnimTime * WalkBobSpeed) * (AnimState == EPlayerAnimState::Run ? RunBobAmount : WalkBobAmount);

	const float PH = PlayerHeight;
	const float BW = BodyWidth;

	const float LArmX = -BW * 0.5f - 0.065f;
	const float RArmX = BW * 0.5f + 0.065f;
	const float ArmPivotY = PH * 0.75f;

	LeftArmMesh->SetRelativeLocation(FVector(LArmX, FMath::Sin(ArmSwing) * 0.15f, ArmPivotY + Bob));
	LeftArmMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(ArmSwing * 0.5f), 0, 0));
	LeftHandMesh->SetRelativeLocation(FVector(LArmX, FMath::Sin(ArmSwing) * 0.25f, PH * 0.53f + Bob));

	RightArmMesh->SetRelativeLocation(FVector(RArmX, FMath::Sin(-ArmSwing) * 0.15f, ArmPivotY + Bob));
	RightArmMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(-ArmSwing * 0.5f), 0, 0));
	RightHandMesh->SetRelativeLocation(FVector(RArmX, FMath::Sin(-ArmSwing) * 0.25f, PH * 0.53f + Bob));

	const float LLegX = -0.08f;
	const float RLegX = 0.08f;
	const float LegPivotY = PH * 0.28f;

	LeftLegMesh->SetRelativeLocation(FVector(LLegX, FMath::Sin(-LegSwing) * 0.12f, LegPivotY + Bob));
	LeftLegMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(-LegSwing * 0.4f), 0, 0));
	LeftShoeMesh->SetRelativeLocation(FVector(LLegX, FMath::Sin(-LegSwing) * 0.18f, PH * 0.02f + Bob));

	RightLegMesh->SetRelativeLocation(FVector(RLegX, FMath::Sin(LegSwing) * 0.12f, LegPivotY + Bob));
	RightLegMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(LegSwing * 0.4f), 0, 0));
	RightShoeMesh->SetRelativeLocation(FVector(RLegX, FMath::Sin(LegSwing) * 0.18f, PH * 0.02f + Bob));

	TorsoMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.65f + Bob));
	HeadMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.91f + Bob));
	HairMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.92f + Bob));
	NeckMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PH * 0.81f + Bob));

	EyeWhiteLeftMesh->SetRelativeLocation(FVector(-0.045f, 0.065f, PH * 0.91f + Bob));
	EyeWhiteRightMesh->SetRelativeLocation(FVector(0.045f, 0.065f, PH * 0.91f + Bob));
	EyeIrisLeftMesh->SetRelativeLocation(FVector(-0.045f, 0.075f, PH * 0.91f + Bob));
	EyeIrisRightMesh->SetRelativeLocation(FVector(0.045f, 0.075f, PH * 0.91f + Bob));
	NoseMesh->SetRelativeLocation(FVector(0.0f, 0.065f, PH * 0.88f + Bob));
	MouthMesh->SetRelativeLocation(FVector(0.0f, 0.065f, PH * 0.865f + Bob));
}
