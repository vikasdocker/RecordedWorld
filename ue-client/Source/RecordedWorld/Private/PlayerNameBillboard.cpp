#include "PlayerNameBillboard.h"
#include "Camera/CameraComponent.h"
#include "Kismet/GameplayStatics.h"

UPlayerNameBillboard::UPlayerNameBillboard()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;

	NameText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("NameText"));
	NameText->SetRelativeLocation(FVector(0.0f, 0.0f, HeightOffset));
	NameText->SetText(FText::FromString(TEXT("Player")));
	NameText->SetTextRenderColor(FLinearColor(0.0f, 1.0f, 0.53f).ToFColor(true));
	NameText->SetCastShadow(false);
}

void UPlayerNameBillboard::BeginPlay()
{
	Super::BeginPlay();

	if (NameText && GetOwner())
	{
		NameText->AttachToComponent(GetOwner()->GetRootComponent(),
			FAttachmentTransformRules::KeepRelativeTransform);
		NameText->SetRelativeLocation(FVector(0.0f, 0.0f, HeightOffset));
	}
}

void UPlayerNameBillboard::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UpdateBillboard();
}

void UPlayerNameBillboard::SetPlayerName(const FString& NewName)
{
	if (NameText)
	{
		NameText->SetText(FText::FromString(NewName));
	}
}

void UPlayerNameBillboard::SetNameColor(const FLinearColor& Color)
{
	if (NameText)
	{
		NameText->SetTextRenderColor(Color.ToFColor(true));
	}
}

void UPlayerNameBillboard::UpdateBillboard()
{
	if (!NameText)
	{
		return;
	}

	APlayerCameraManager* CamManager = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!CamManager)
	{
		return;
	}

	const FVector CamLocation = CamManager->GetCameraLocation();
	const FVector TextLocation = NameText->GetComponentLocation();
	const FRotator LookAtRotation = (CamLocation - TextLocation).Rotation();

	NameText->SetWorldRotation(LookAtRotation);
}
