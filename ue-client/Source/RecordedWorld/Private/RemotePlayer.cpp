#include "RemotePlayer.h"
#include "PlayerNameBillboard.h"
#include "Materials/Material.h"

ARemotePlayer::ARemotePlayer()
{
	PrimaryActorTick.bCanEverTick = true;

	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent->SetMobility(EComponentMobility::Movable);

	BodyRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BodyRoot"));
	BodyRoot->SetupAttachment(RootComponent);

	TorsoMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("TorsoMesh"));
	TorsoMesh->SetupAttachment(BodyRoot);
	HeadMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("HeadMesh"));
	HeadMesh->SetupAttachment(BodyRoot);
	LeftArmMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("LeftArmMesh"));
	LeftArmMesh->SetupAttachment(BodyRoot);
	RightArmMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RightArmMesh"));
	RightArmMesh->SetupAttachment(BodyRoot);
	LeftLegMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("LeftLegMesh"));
	LeftLegMesh->SetupAttachment(BodyRoot);
	RightLegMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RightLegMesh"));
	RightLegMesh->SetupAttachment(BodyRoot);

	NameBillboard = CreateDefaultSubobject<UPlayerNameBillboard>(TEXT("NameBillboard"));

	TargetPosition = FVector::ZeroVector;
}

void ARemotePlayer::BeginPlay()
{
	Super::BeginPlay();
	BuildBody(FLinearColor(0.0f, 1.0f, 0.53f));
	ApplyBodyMaterial();
}

void ARemotePlayer::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	const FVector CurrentLocation = GetActorLocation();
	const FVector SmoothedPos = FMath::VInterpTo(CurrentLocation, TargetPosition, DeltaTime, LerpSpeed);
	SetActorLocation(SmoothedPos);

	CurrentRotation = FMath::FInterpTo(CurrentRotation, TargetRotation, DeltaTime, LerpSpeed);
	SetActorRotation(FRotator(0.0f, CurrentRotation, 0.0f));

	const float Speed = FVector(TargetPosition - CurrentLocation).Size() / DeltaTime;
	const float SpeedFactor = FMath::Clamp(Speed / 600.0f, 0.0f, 1.0f);
	AnimTime += DeltaTime * SpeedFactor * 8.0f;

	const float ArmSwing = FMath::Sin(AnimTime) * 0.3f * SpeedFactor;
	LeftArmMesh->SetRelativeLocation(FVector(-BodyWidth * 0.5f - 0.065f, FMath::Sin(ArmSwing) * 0.15f, PlayerHeight * 0.75f));
	LeftArmMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(ArmSwing * 0.5f), 0, 0));
	RightArmMesh->SetRelativeLocation(FVector(BodyWidth * 0.5f + 0.065f, FMath::Sin(-ArmSwing) * 0.15f, PlayerHeight * 0.75f));
	RightArmMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(-ArmSwing * 0.5f), 0, 0));

	const float LegSwing = FMath::Sin(AnimTime) * 0.25f * SpeedFactor;
	LeftLegMesh->SetRelativeLocation(FVector(-0.08f, FMath::Sin(-LegSwing) * 0.12f, PlayerHeight * 0.28f));
	LeftLegMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(-LegSwing * 0.4f), 0, 0));
	RightLegMesh->SetRelativeLocation(FVector(0.08f, FMath::Sin(LegSwing) * 0.12f, PlayerHeight * 0.28f));
	RightLegMesh->SetRelativeRotation(FRotator(FMath::RadiansToDegrees(LegSwing * 0.4f), 0, 0));
}

void ARemotePlayer::InitPlayer(const FString& InUsername, const FLinearColor& InColor)
{
	Username = InUsername;
	BuildBody(InColor);
	ApplyBodyMaterial();

	if (NameBillboard)
	{
		NameBillboard->SetPlayerName(InUsername);
		NameBillboard->SetNameColor(InColor);
	}
}

void ARemotePlayer::UpdatePosition(const FVector& NewPosition, float NewRotation)
{
	TargetPosition = NewPosition;
	TargetRotation = NewRotation;
}

void ARemotePlayer::UpdateColor(const FLinearColor& NewColor)
{
	BuildBody(NewColor);
}

void ARemotePlayer::BuildBody(const FLinearColor& ShirtColor)
{
	const FLinearColor SkinColor = FLinearColor(1.0f, 0.86f, 0.67f);
	const FLinearColor PantsColor = FLinearColor(0.165f, 0.2f, 0.267f);

	AddMeshBox(TorsoMesh, FVector(BodyWidth * 0.5f, 0.09f, 0.26f), ShirtColor);
	TorsoMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PlayerHeight * 0.65f));

	AddMeshSphere(HeadMesh, 0.13f, SkinColor, 10);
	HeadMesh->SetRelativeLocation(FVector(0.0f, 0.0f, PlayerHeight * 0.91f));

	AddMeshBox(LeftArmMesh, FVector(0.045f, 0.045f, 0.21f), ShirtColor);
	LeftArmMesh->SetRelativeLocation(FVector(-BodyWidth * 0.5f - 0.065f, 0.0f, PlayerHeight * 0.75f));

	AddMeshBox(RightArmMesh, FVector(0.045f, 0.045f, 0.21f), ShirtColor);
	RightArmMesh->SetRelativeLocation(FVector(BodyWidth * 0.5f + 0.065f, 0.0f, PlayerHeight * 0.75f));

	AddMeshBox(LeftLegMesh, FVector(0.055f, 0.055f, 0.24f), PantsColor);
	LeftLegMesh->SetRelativeLocation(FVector(-0.08f, 0.0f, PlayerHeight * 0.28f));

	AddMeshBox(RightLegMesh, FVector(0.055f, 0.055f, 0.24f), PantsColor);
	RightLegMesh->SetRelativeLocation(FVector(0.08f, 0.0f, PlayerHeight * 0.28f));
}

void ARemotePlayer::ApplyBodyMaterial()
{
	UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/Materials/M_VertexColor.M_VertexColor"));

	if (!Mat)
	{
		Mat = UMaterial::GetDefaultMaterial(MD_Surface);
	}

	TArray<UProceduralMeshComponent*> BodyMeshes = {
		TorsoMesh, HeadMesh, LeftArmMesh, RightArmMesh, LeftLegMesh, RightLegMesh
	};

	for (UProceduralMeshComponent* Mesh : BodyMeshes)
	{
		if (Mesh)
		{
			Mesh->SetMaterial(0, Mat);
		}
	}
}

void ARemotePlayer::AddMeshBox(UProceduralMeshComponent* Comp, const FVector& Size, const FLinearColor& Color)
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

void ARemotePlayer::AddMeshSphere(UProceduralMeshComponent* Comp, float Radius, const FLinearColor& Color, int32 Segments)
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
			Vertices.Add(FVector(SinPhi * FMath::Cos(Theta) * Radius, SinPhi * FMath::Sin(Theta) * Radius, CosPhi * Radius));
			Normals.Add(FVector(SinPhi * FMath::Cos(Theta), SinPhi * FMath::Sin(Theta), CosPhi).GetSafeNormal());
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
			Triangles.Add(I0); Triangles.Add(I2); Triangles.Add(I1);
			Triangles.Add(I1); Triangles.Add(I2); Triangles.Add(I3);
		}
	}

	Comp->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors,
		TArray<FProcMeshTangent>(), false);
}
